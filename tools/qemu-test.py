#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Boot a Beamline disk image under QEMU and wait for a serial marker (docs/spec.md §25-29).

The image is never written: every run boots a throwaway qcow2 overlay (§28).
Acceleration is picked automatically (QEMU_ACCEL=auto|hvf|kvm|tcg, §25):
macOS -> HVF, Linux with a usable /dev/kvm -> KVM, otherwise TCG.

Examples:
  tools/qemu-test.py --image out/aarch64/virt/disk.raw
  tools/qemu-test.py --image out/aarch64/virt/disk.raw --interactive

Standard library only.
"""

import argparse
import base64
import os
import platform
import re
import shutil
import subprocess
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

DEV_PASSWORD = "dev"  # Interactive debugging only; supplied as a credential, never baked in.


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

    cmd = [
        binary,
        "-machine", f"{machine},accel={accel}",
        "-cpu", cpu,
        "-smp", str(args.cpus),
        "-m", args.memory,
        "-no-reboot",
        "-drive", f"if=pflash,format=raw,unit=0,readonly=on,file={code}",
        "-drive", f"if=pflash,format=raw,unit=1,file={vars_path}",
        # Virtual hardware contract (docs/spec.md §4).
        "-drive", f"if=none,id=disk0,format=qcow2,file={overlay}",
        "-device", "virtio-blk-pci,drive=disk0",
        "-netdev", "user,id=net0",
        "-device", "virtio-net-pci,netdev=net0",
        "-device", "virtio-rng-pci",
    ]
    if args.interactive:
        # Serial and monitor multiplexed on this terminal (Ctrl-a c / Ctrl-a x).
        cmd += ["-nographic"]
        cmd += credential_args("passwd.plaintext-password.dev", DEV_PASSWORD)
    else:
        cmd += ["-display", "none", "-monitor", "none", "-serial", "stdio"]
    return cmd


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


def run_test(cmd, args):
    log = open(args.log, "w", encoding="utf-8") if args.log else None
    expect = re.compile(args.expect)
    result = {"status": None}
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def reader():
        for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace")
            sys.stdout.write(line)
            sys.stdout.flush()
            if log:
                log.write(line)
            plain = ANSI_ESCAPE.sub("", line).strip()
            if result["status"] is None:
                if expect.search(plain):
                    result["status"] = "pass"
                elif any(p.search(plain) for p in FAILURE_PATTERNS):
                    result["status"] = "fail: " + plain

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    deadline = time.monotonic() + args.timeout
    while result["status"] is None and proc.poll() is None and time.monotonic() < deadline:
        time.sleep(0.2)

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


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", required=True, help="raw disk image (never modified)")
    parser.add_argument("--arch", default=host_arch(), choices=sorted(FIRMWARE_CODE))
    parser.add_argument("--accel", default=os.environ.get("QEMU_ACCEL", "auto"),
                        choices=["auto", "hvf", "kvm", "tcg"])
    parser.add_argument("--expect", default="BEAMLINE_BOOT_OK", help="regex that marks success on the serial console")
    parser.add_argument("--timeout", type=int, default=None, help="seconds (default 300, 1200 under TCG)")
    parser.add_argument("--memory", default="2G")
    parser.add_argument("--cpus", type=int, default=4)
    parser.add_argument("--disk-size", default="8G", help="virtual size of the overlay")
    parser.add_argument("--log", help="also write the serial console to this file")
    parser.add_argument("--interactive", action="store_true",
                        help="attach the serial console to this terminal; dev/dev can log in (Ctrl-a x quits)")
    args = parser.parse_args()

    if not os.path.isfile(args.image):
        sys.exit(f"qemu-test: image {args.image} not found")
    accel = pick_accel(args.accel, args.arch)
    if args.timeout is None:
        args.timeout = 1200 if accel == "tcg" else 300

    with tempfile.TemporaryDirectory(prefix="beamline-qemu-") as workdir:
        overlay = create_overlay(args.image, workdir, args.disk_size)
        cmd = qemu_command(args, accel, workdir, overlay)
        print(f"qemu-test: accel={accel} arch={args.arch} image={args.image}", file=sys.stderr)
        if args.interactive:
            return subprocess.call(cmd)
        status = run_test(cmd, args)

    print(f"qemu-test: {status}", file=sys.stderr)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
