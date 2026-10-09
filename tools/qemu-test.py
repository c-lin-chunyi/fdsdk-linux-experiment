#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Boot a Beamline disk image under QEMU and wait for a serial marker (docs/spec.md §25-29).

The image is never written: every run boots a throwaway qcow2 overlay (§28).
Acceleration is picked automatically (QEMU_ACCEL=auto|hvf|kvm|tcg, §25):
macOS -> HVF, Linux with a usable /dev/kvm -> KVM, otherwise TCG. --qemu (or QEMU_SYSTEM)
selects another QEMU binary, such as one built with virglrenderer for --gpu gl.

Examples:
  tools/qemu-test.py --image out/aarch64/virt/disk.raw
  tools/qemu-test.py --image out/aarch64/virt/disk.raw --interactive
  tools/qemu-test.py --image out/aarch64/virt/disk.raw --interactive --gpu gl \
      --qemu /path/to/qemu-system-aarch64        # a virglrenderer QEMU: accelerated GNOME

Standard library only.
"""

import argparse
import base64
import json
import os
import platform
import re
import shutil
import socket
import struct
import subprocess
import zlib
import sys
import tempfile
import threading
import time

FIRMWARE_CODE = {
    "aarch64": [
        "/opt/homebrew/share/qemu/edk2-aarch64-code.fd",
        "/usr/local/share/qemu/edk2-aarch64-code.fd",
        "/usr/share/qemu/edk2-aarch64-code.fd",
        "/usr/share/edk2/aarch64/QEMU_EFI-pflash.raw",
        "/usr/share/AAVMF/AAVMF_CODE.fd",
    ],
    "x86_64": [
        "/opt/homebrew/share/qemu/edk2-x86_64-code.fd",
        "/usr/local/share/qemu/edk2-x86_64-code.fd",
        "/usr/share/qemu/edk2-x86_64-code.fd",
        "/usr/share/edk2/ovmf/OVMF_CODE.fd",
        "/usr/share/OVMF/OVMF_CODE_4M.fd",
        "/usr/share/OVMF/OVMF_CODE.fd",
    ],
}

# Vars templates; aarch64 firmware works with a zero-filled store of the code's size.
FIRMWARE_VARS = {
    "aarch64": [],
    "x86_64": [
        "/opt/homebrew/share/qemu/edk2-i386-vars.fd",
        "/usr/local/share/qemu/edk2-i386-vars.fd",
        "/usr/share/qemu/edk2-i386-vars.fd",
        "/usr/share/edk2/ovmf/OVMF_VARS.fd",
        "/usr/share/OVMF/OVMF_VARS_4M.fd",
        "/usr/share/OVMF/OVMF_VARS.fd",
    ],
}

# A green boot reaches the marker without any failed unit (docs/spec.md §17.1): systemd's
# [FAILED]/[DEPEND] status lines count as failures, not just panics.
FAILURE_PATTERNS = [
    re.compile(r"Kernel panic - not syncing"),
    re.compile(r"You are in emergency mode"),
    re.compile(r"^\[FAILED\] "),
    re.compile(r"^\[DEPEND\] "),
]

# systemd colours its status column; match against the plain text.
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;:?]*[A-Za-z]")

# Human accounts are systemd-homed users (docs/spec.md §18.3, docs/decisions.md D54), not part
# of the image: systemd-homed-firstboot creates them on the first boot from these
# home.create.* credentials. dev (wheel) and alice (no privileges); the documented test
# passwords equal the user names (SHA-512 crypt hashes: openssl passwd -6 -salt
# beamline.<name> <name>). LUKS2 home images holding btrfs, with a light PBKDF so a 2 GB VM
# boots quickly; real accounts use homed's defaults.
PASSWORD_HASHES = {
    "dev": "$6$beamline.dev$jzZS2L71jkPcmXY707t/JgYaVU7k5.aklWW9v41mK7QWSPIaN13d./XW.5vPZWYhWt35"
           ".pn2PKzS2dJAd920I0",
    "alice": "$6$beamline.alice$6jP0aHslE7bNkSp3OayK47HO/UIbt9x7.BzT2Bl.M0zWP/b2iC4/aAttUeSLm0Kb6a"
             "31ou35kizzjawy8faS1/",
}


def home_record(name, uid, real_name, groups, size):
    return {
        "userName": name,
        "uid": uid,
        "realName": real_name,
        "disposition": "regular",
        "shell": "/usr/bin/sh",
        "memberOf": groups,
        "storage": "luks",
        "fileSystemType": "btrfs",
        "diskSize": size,
        "enforcePasswordPolicy": False,
        "luksPbkdfType": "argon2id",
        "luksPbkdfMemoryCost": 64 * 1024 * 1024,
        "luksPbkdfTimeCostUSec": 100000,
        "privileged": {"hashedPassword": [PASSWORD_HASHES[name]]},
        "secret": {"password": [name]},
    }


HOMES = {
    "dev": home_record("dev", 60001, "Developer", ["wheel"], 2 * 1024 ** 3),
    "alice": home_record("alice", 60002, "Alice", [], 1024 ** 3),
}


def host_arch():
    machine = platform.machine().lower()
    return {"arm64": "aarch64", "amd64": "x86_64"}.get(machine, machine)


def pick_accel(requested, arch):
    if requested != "auto":
        return requested
    if arch != host_arch():
        return "tcg"
    if sys.platform == "darwin":
        return "hvf"
    if os.access("/dev/kvm", os.R_OK | os.W_OK):
        return "kvm"
    return "tcg"


def find_file(env_var, candidates, what):
    override = os.environ.get(env_var)
    if override:
        if not os.path.exists(override):
            sys.exit(f"qemu-test: {env_var}={override} does not exist")
        return override
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    sys.exit(f"qemu-test: no {what} found; set {env_var}")


def qemu_command(args, accel, workdir, overlay):
    arch = args.arch
    code = find_file("QEMU_FIRMWARE_CODE", FIRMWARE_CODE[arch], f"{arch} UEFI firmware")
    vars_path = os.path.join(workdir, "efivars.fd")
    if FIRMWARE_VARS[arch]:
        shutil.copyfile(find_file("QEMU_FIRMWARE_VARS", FIRMWARE_VARS[arch], f"{arch} UEFI vars"), vars_path)
    else:
        with open(vars_path, "wb") as f:
            f.truncate(os.path.getsize(code))

    cpu = "host" if accel in ("hvf", "kvm") else "max"
    if arch == "aarch64":
        binary, machine = "qemu-system-aarch64", "virt"
    else:
        binary, machine = "qemu-system-x86_64", "q35,smm=off"
    binary = args.qemu or os.environ.get("QEMU_SYSTEM") or binary

    cmd = [
        binary,
        "-machine", f"{machine},accel={accel}",
        "-cpu", cpu,
        "-smp", str(args.cpus),
        "-m", args.memory,
        "-drive", f"if=pflash,format=raw,unit=0,readonly=on,file={code}",
        "-drive", f"if=pflash,format=raw,unit=1,file={vars_path}",
        # Virtual hardware contract (docs/spec.md §4).
        "-drive", f"if=none,id=disk0,format=qcow2,file={overlay}",
        "-device", "virtio-blk-pci,drive=disk0",
        "-netdev", "user,id=net0",
        "-device", "virtio-net-pci,netdev=net0",
        "-device", "virtio-rng-pci",
    ]
    if not args.reboot:
        # A guest reboot ends QEMU, so a test that did not ask for reboots cannot loop.
        cmd += ["-no-reboot"]
    if args.gpu != "none":
        # docs/spec.md §30: 2D virtio-gpu with software rendering for automated tests;
        # virgl (gl) for interactive sessions with a QEMU built with virglrenderer.
        cmd += ["-device", "virtio-gpu-gl-pci" if args.gpu == "gl" else "virtio-gpu-pci",
                "-device", "virtio-keyboard-pci", "-device", "virtio-tablet-pci"]
    if args.interactive and args.gpu != "none":
        # A window for the session; serial and monitor stay on this terminal.
        cmd += ["-display", "sdl,gl=es" if args.gpu == "gl" else "cocoa" if sys.platform == "darwin" else "sdl",
                "-serial", "mon:stdio"]
    elif args.interactive:
        # Serial and monitor multiplexed on this terminal (Ctrl-a c / Ctrl-a x).
        cmd += ["-nographic"]
    else:
        cmd += ["-display", "none", "-monitor", "none", "-serial", "stdio",
                "-qmp", f"unix:{os.path.join(workdir, 'qmp.sock')},server=on,wait=off"]
    for name, record in HOMES.items():
        cmd += credential_args(f"home.create.{name}", json.dumps(record))
    for i, spec in enumerate(args.attach_tampered):
        src, mode = spec.rsplit(":", 1)
        copy = tampered_copy(src, mode, workdir, arch)
        # Visible in the guest as /dev/disk/by-id/virtio-tamper-<mode>.
        cmd += ["-drive", f"if=none,id=tamper{i},format=raw,readonly=on,file={copy}",
                "-device", f"virtio-blk-pci,drive=tamper{i},serial=tamper-{mode}"]
    for spec in args.credential:
        name, value = spec.split("=", 1)
        cmd += credential_args(name, value)
    for spec in args.credential_file:
        name, path = spec.split("=", 1)
        with open(path, encoding="utf-8") as f:
            cmd += credential_args(name, f.read())
    for path in args.extra_unit:
        with open(path, encoding="utf-8") as f:
            cmd += credential_args(f"systemd.extra-unit.{os.path.basename(path)}", f.read())
    extra = [f"systemd.wants={unit}" for unit in args.wants] + args.kernel_arg
    if extra:
        # systemd-stub appends this to the UKI's command line (no Secure Boot yet).
        cmd += ["-smbios", f"type=11,value=io.systemd.stub.kernel-cmdline-extra={' '.join(extra)}"]
    return cmd


def qmp(workdir, *commands):
    """Run QMP commands on the test VM; the first error, or None."""
    with socket.socket(socket.AF_UNIX) as s:
        s.connect(os.path.join(workdir, "qmp.sock"))
        f = s.makefile("rw")
        f.readline()                                              # greeting
        for command in ({"execute": "qmp_capabilities"},) + commands:
            f.write(json.dumps(command) + "\n")
            f.flush()
            while True:
                reply = json.loads(f.readline())
                if "event" not in reply:
                    break
            if "error" in reply:
                return reply["error"].get("desc")
    return None


# QEMU key codes for the characters test sign-ins type.
QCODES = {**{c: c for c in "abcdefghijklmnopqrstuvwxyz0123456789"},
          " ": "spc", "\n": "ret", "\t": "tab", ".": "dot", "-": "minus", "/": "slash"}


def type_text(workdir, text):
    """Type text on the virtual keyboard: characters (an upper-case letter with shift), and
    named keys as {down}, {up}, {ret}, {tab} or {esc}."""
    for token in re.findall(r"\{[a-z]+\}|.", text, re.S):
        if token.startswith("{") and len(token) > 1:
            keys = [{"type": "qcode", "data": token[1:-1]}]
        else:
            keys = [{"type": "qcode", "data": QCODES[token.lower()]}]
            if token.isupper():
                keys.insert(0, {"type": "qcode", "data": "shift"})
        error = qmp(workdir, {"execute": "send-key", "arguments": {"keys": keys, "hold-time": 40}})
        if error:
            print(f"qemu-test: typing failed: {error}", file=sys.stderr)
            return
        time.sleep(0.05)
    print(f"qemu-test: typed {text!r}", file=sys.stderr)


def screendump(workdir, path):
    """Capture the guest display through QMP and fail on a blank (uniform) image."""
    error = qmp(workdir, {"execute": "screendump", "arguments": {"filename": os.path.abspath(path)}})
    if error:
        return f"fail: screendump: {error}"
    with open(path, "rb") as img:
        data = img.read()
    # Binary PPM: "P6\n<width> <height>\n<maxval>\n" then RGB triplets.
    header = data.split(b"\n", 3)
    if len(header) < 4 or header[0] != b"P6":
        return "fail: screendump is not a binary PPM"
    pixels = header[3]
    colours = {pixels[i:i + 3] for i in range(0, len(pixels) - 2, 3 * 97)}
    if len(colours) < 8:
        return f"fail: screendump {path} is blank ({len(colours)} colours)"
    print(f"qemu-test: screendump {path} ({header[1].decode()}, {len(colours)}+ colours)", file=sys.stderr)
    return "pass"


def credential_args(name, value):
    """Pass a systemd system credential through SMBIOS type 11."""
    encoded = base64.b64encode(value.encode()).decode()
    return ["-smbios", f"type=11,value=io.systemd.credential.binary:{name}={encoded}"]


def create_overlay(image, workdir, size):
    overlay = os.path.join(workdir, "overlay.qcow2")
    cmd = ["qemu-img", "create", "-q", "-f", "qcow2", "-F", "raw", "-b", os.path.abspath(image), overlay]
    if size:
        cmd.append(size)
    subprocess.run(cmd, check=True)
    return overlay


# Discoverable Partitions Specification: the root partition type of each architecture.
ROOT_TYPE = {"aarch64": "b921b045-1df0-41c3-af44-4c6f280d3fae",
             "x86_64": "4f68bce3-e8cd-4db1-96e7-fbcaf984b709"}


LINUX_GENERIC_TYPE = "0fc63daf-8483-4772-8e79-3d69d8477de4"


def guid_to_str(raw):
    a, b, c = struct.unpack_from("<IHH", raw, 0)
    return f"{a:08x}-{b:04x}-{c:04x}-{raw[8:10].hex()}-{raw[10:16].hex()}"


def str_to_guid(text):
    h = text.replace("-", "")
    return struct.pack("<IHH", int(h[0:8], 16), int(h[8:12], 16), int(h[12:16], 16)) + bytes.fromhex(h[16:])


def gpt_entries(image):
    """The primary GPT (512-byte sectors): header, and per partition its table offset, type,
    label and byte range."""
    with open(image, "rb") as f:
        f.seek(512)
        header = f.read(512)
        if header[:8] != b"EFI PART":
            sys.exit(f"qemu-test: {image} has no GPT")
        entries_lba, count, entry_size = struct.unpack_from("<QII", header, 72)
        f.seek(entries_lba * 512)
        table = f.read(count * entry_size)
    parts = []
    for i in range(count):
        entry = table[i * entry_size:(i + 1) * entry_size]
        if entry[:16] == bytes(16):
            continue
        first, last = struct.unpack_from("<QQ", entry, 32)
        parts.append({"entry": entries_lba * 512 + i * entry_size, "type": guid_to_str(entry[:16]),
                      "label": entry[56:128].decode("utf-16-le").rstrip("\0"),
                      "offset": first * 512, "size": (last - first + 1) * 512})
    return header, entries_lba, count, entry_size, parts


def gpt_partition(image, wanted, arch):
    """Byte offset of a GPT partition: the one with this label, or with `root`, the first root
    partition of the architecture (SYSTEM-A)."""
    for part in gpt_entries(image)[4]:
        if part["label"] == wanted or (wanted == "root" and part["type"] == ROOT_TYPE[arch]):
            return part["offset"]
    sys.exit(f"qemu-test: no partition {wanted} in {image}")


def tampered_copy(src, mode, workdir, arch):
    """A modified copy of an extension image, in the test's own directory (§28):
      signature  one character of the root hash signature changed (still valid JSON)
      data       the first block of the EROFS partition overwritten
      unsigned   the signature partition retyped as generic data, so the image is unsigned"""
    dest = os.path.join(workdir, f"tampered-{mode}.raw")
    shutil.copyfile(src, dest)
    header, entries_lba, count, entry_size, parts = gpt_entries(dest)
    data = next(p for p in parts if p["type"] == ROOT_TYPE[arch])
    sig = next(p for p in parts if p["label"].endswith("-verity-sig"))
    with open(dest, "r+b") as f:
        if mode == "data":
            f.seek(data["offset"])
            f.write(b"\x5a" * 4096)
        elif mode == "signature":
            f.seek(sig["offset"])
            blob = f.read(sig["size"])
            at = blob.index(b'"signature":"') + len(b'"signature":"') + 16
            f.seek(sig["offset"] + at)
            f.write(b"B" if blob[at:at + 1] == b"A" else b"A")
        elif mode == "unsigned":
            f.seek(sig["entry"])
            f.write(str_to_guid(LINUX_GENERIC_TYPE))
            f.seek(entries_lba * 512)
            table = f.read(count * entry_size)
            header = bytearray(header[:struct.unpack_from("<I", header, 12)[0]])
            struct.pack_into("<I", header, 88, zlib.crc32(table))
            struct.pack_into("<I", header, 16, 0)
            struct.pack_into("<I", header, 16, zlib.crc32(header))
            f.seek(512)
            f.write(header)
        else:
            sys.exit(f"qemu-test: unknown tamper mode {mode}")
    return dest


def tamper(image, overlay, label, arch):
    """Corrupt the first block of a partition in the throwaway overlay, never the image (§28)."""
    offset = gpt_partition(image, label, arch)
    subprocess.run(["qemu-io", "-f", "qcow2", "-c", f"write -P 0x5a {offset} 4096", overlay],
                   check=True, stdout=subprocess.DEVNULL)
    print(f"qemu-test: tampered with {label} at byte {offset} (overlay only)", file=sys.stderr)


def run_test(cmd, args, workdir=None):
    log = open(args.log, "w", encoding="utf-8") if args.log else None
    expect = re.compile(args.expect)
    fail_on = [re.compile(p) for p in args.fail_on]
    # --type REGEX::SECONDS::TEXT: once REGEX appears, type TEXT that many seconds later.
    typing = []
    for spec in args.type:
        pattern, delay, text = spec.split("::", 2)
        typing.append([re.compile(pattern), float(delay), text.replace("\\n", "\n"), False])
    required = {pattern: re.compile(pattern) for pattern in args.require}
    seen = set()
    result = {"status": None}
    script = load_serial_script(args.serial_script) if args.serial_script else []
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE if script else subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    # The serial script reads the console as a stream: prompts such as "login:" end without a
    # newline. Text before the last match is consumed, so one prompt satisfies one expect.
    stream = {"text": ""}

    def advance_script(text):
        stream["text"] = (stream["text"] + ANSI_ESCAPE.sub("", text))[-8192:]
        while script:
            kind, value = script[0]
            if kind == "send":
                proc.stdin.write(value.encode())
                proc.stdin.flush()
                script.pop(0)
                continue
            match = value.search(stream["text"])
            if not match:
                break
            stream["text"] = stream["text"][match.end():]
            script.pop(0)

    def lines():
        # Complete lines for the line-based checks; partial text still feeds the script.
        pending = b""
        while True:
            chunk = os.read(proc.stdout.fileno(), 4096)
            if not chunk:
                break
            if script:
                advance_script(chunk.decode("utf-8", errors="replace"))
            pending += chunk
            *complete, pending = pending.split(b"\n")
            for raw in complete:
                yield raw + b"\n"
        if pending:
            yield pending

    def reader():
        for raw in lines():
            line = raw.decode("utf-8", errors="replace")
            sys.stdout.write(line)
            sys.stdout.flush()
            if log:
                log.write(line)
            plain = ANSI_ESCAPE.sub("", line).strip()
            seen.update(name for name, p in required.items() if p.search(plain))
            for step in typing:
                if not step[3] and workdir and step[0].search(plain):
                    step[3] = True
                    threading.Timer(step[1], type_text, (workdir, step[2])).start()
            if result["status"] is None:
                if expect.search(plain) and not script:
                    missing = sorted(set(required) - seen)
                    result["status"] = f"fail: '{args.expect}' before {', '.join(missing)}" if missing else "pass"
                elif any(p.search(plain) for p in fail_on) or (
                        not (args.tamper or args.allow_failures) and any(p.search(plain) for p in FAILURE_PATTERNS)):
                    result["status"] = "fail: " + plain

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    deadline = time.monotonic() + args.timeout
    while result["status"] is None and proc.poll() is None and time.monotonic() < deadline:
        time.sleep(0.2)
    if result["status"] == "pass" and args.screendump and workdir:
        time.sleep(args.screendump_delay)
        result["status"] = screendump(workdir, args.screendump)

    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    thread.join(timeout=5)
    if log:
        log.close()

    status = result["status"]
    if status is None:
        status = f"fail: QEMU exited with {proc.returncode}" if time.monotonic() < deadline else \
            f"fail: no '{args.expect}' within {args.timeout}s"
    return status


def load_serial_script(path):
    """A serial console script: `expect REGEX` and `send TEXT` lines, in order (\\n in TEXT is a
    newline). Blank lines and lines starting with # are ignored."""
    steps = []
    with open(path, encoding="utf-8") as f:
        for number, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            kind, _, value = line.partition(" ")
            if kind == "expect":
                steps.append(("expect", re.compile(value)))
            elif kind == "send":
                steps.append(("send", value.replace("\\n", "\n")))
            else:
                sys.exit(f"qemu-test: {path}:{number}: expected `expect` or `send`")
    return steps


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", required=True, help="raw disk image (never modified)")
    parser.add_argument("--arch", default=host_arch(), choices=sorted(FIRMWARE_CODE))
    parser.add_argument("--accel", default=os.environ.get("QEMU_ACCEL", "auto"),
                        choices=["auto", "hvf", "kvm", "tcg"])
    parser.add_argument("--expect", default="BEAMLINE_BOOT_OK", help="regex that marks success on the serial console")
    parser.add_argument("--require", action="append", default=[], metavar="REGEX",
                        help="regex that must appear before --expect (repeatable)")
    parser.add_argument("--extra-unit", action="append", default=[], metavar="FILE",
                        help="unit file to inject as a systemd.extra-unit credential (repeatable)")
    parser.add_argument("--wants", action="append", default=[], metavar="UNIT",
                        help="unit to pull in through the kernel command line (repeatable)")
    parser.add_argument("--kernel-arg", action="append", default=[], metavar="ARG",
                        help="extra kernel command line argument (repeatable)")
    parser.add_argument("--gpu", choices=["none", "2d", "gl"], default="none",
                        help="virtual GPU: 2d virtio-gpu (software rendering), gl virgl (interactive)")
    parser.add_argument("--qemu", help="QEMU system emulator binary (default from PATH, or QEMU_SYSTEM)")
    parser.add_argument("--serial-script", metavar="FILE",
                        help="drive the serial console: `expect REGEX` / `send TEXT` lines; --expect "
                             "only counts once the script has finished")
    parser.add_argument("--type", action="append", default=[], metavar="REGEX::SECONDS::TEXT",
                        help="once REGEX appears on the console, type TEXT on the virtual keyboard after "
                             "SECONDS (named keys as {down}, {ret}, ...; repeatable; needs --gpu)")
    parser.add_argument("--screendump", metavar="PPM",
                        help="after --expect, capture the display here and fail if it is blank")
    parser.add_argument("--screendump-delay", type=float, default=5.0,
                        help="seconds to wait before the capture (default 5)")
    parser.add_argument("--timeout", type=int, default=None, help="seconds (default 300, 1200 under TCG)")
    parser.add_argument("--tamper", metavar="LABEL",
                        help="corrupt the first block of the GPT partition with this label (or `root`: the "
                             "first root partition, SYSTEM-A) in the overlay; the boot is expected to fail, so "
                             "failed units do not end the test (--expect names the failure)")
    parser.add_argument("--credential", action="append", default=[], metavar="NAME=VALUE",
                        help="pass a system credential (repeatable)")
    parser.add_argument("--credential-file", action="append", default=[], metavar="NAME=FILE",
                        help="pass a file's contents as a system credential (repeatable)")
    parser.add_argument("--allow-failures", action="store_true",
                        help="failed units do not end the test (tests that make boots fail on purpose)")
    parser.add_argument("--fail-on", action="append", default=[], metavar="REGEX",
                        help="a console line that fails the test at once, even with --allow-failures (repeatable)")
    parser.add_argument("--attach-tampered", action="append", default=[], metavar="IMAGE:MODE",
                        help="attach a tampered copy of an extension image (MODE: signature, data, "
                             "unsigned) as /dev/disk/by-id/virtio-tamper-MODE (repeatable)")
    parser.add_argument("--reboot", action="store_true",
                        help="let the guest reboot (same overlay, same credentials) instead of ending QEMU")
    parser.add_argument("--memory", default="2G")
    parser.add_argument("--cpus", type=int, default=4)
    parser.add_argument("--disk-size", default="16G",
                        help="virtual size of the overlay; DATA grows into it at first boot")
    parser.add_argument("--log", help="also write the serial console to this file")
    parser.add_argument("--interactive", action="store_true",
                        help="attach the serial console to this terminal; dev/dev or alice/alice can log in (Ctrl-a x quits)")
    args = parser.parse_args()

    if not os.path.isfile(args.image):
        sys.exit(f"qemu-test: image {args.image} not found")
    accel = pick_accel(args.accel, args.arch)
    if args.timeout is None:
        args.timeout = 1200 if accel == "tcg" else 300

    with tempfile.TemporaryDirectory(prefix="beamline-qemu-") as workdir:
        overlay = create_overlay(args.image, workdir, args.disk_size)
        if args.tamper:
            tamper(args.image, overlay, args.tamper, args.arch)
        cmd = qemu_command(args, accel, workdir, overlay)
        print(f"qemu-test: accel={accel} arch={args.arch} image={args.image}", file=sys.stderr)
        if args.interactive:
            return subprocess.call(cmd)
        status = run_test(cmd, args, workdir)

    print(f"qemu-test: {status}", file=sys.stderr)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
