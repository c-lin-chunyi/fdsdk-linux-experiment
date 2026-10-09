#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Static policy checks for Beamline trees and unit files (docs/spec.md §2.1, §6, §18.1).

  --units DIR...      Reject shell constructs in Exec*= lines of unit files.
  --tree SYSROOT      The base root: reject bash, su/sudo/pkexec/doas, package managers and a non-dash
                      /usr/bin/sh; also apply the --artifact rules.
  --artifact TREE...  Any final artifact (root, extension): reject su/sudo/pkexec/doas, package managers,
                      dracut, GNU coreutils binaries (§7.2) and web engines (§7.1).

Standard library only: this runs on macOS, in the builder VM and inside BuildStream.
"""

import argparse
import os
import re
import sys

EXEC_KEY = re.compile(r"^\s*(Exec(Start|StartPre|StartPost|Stop|StopPost|Reload|Condition))\s*=\s*(.*)$")

# Constructs that mean "this unit is a shell script" (docs/spec.md §6).
SHELL_CONSTRUCTS = [
    # Exec lines may carry the prefixes - @ : + ! before the binary path.
    (re.compile(r"(^|[\s;@:+!-])(/usr)?/bin/(ba|da)?sh\s+-\w*c"), "shell -c"),
    (re.compile(r"(^|[\s;@:+!-])(ba|da)?sh\s+-\w*c\b"), "shell -c"),
    (re.compile(r"\|\|"), "||"),
    (re.compile(r"&&"), "&&"),
    (re.compile(r"(?<!\|)\|(?!\|)"), "pipe"),
    (re.compile(r"\$\("), "$()"),
    (re.compile(r"`"), "backtick"),
]

UNIT_SUFFIXES = (".service", ".socket", ".timer", ".path", ".mount", ".target")

# docs/spec.md §7.1, docs/decisions.md D29: no web engine or web JavaScript engine.
WEB_ENGINE = re.compile(r"^(libwebkit\S*gtk\S*\.so.*|libjavascriptcoregtk\S*\.so.*|"
                        r"(WebKit|WebKit2|JavaScriptCore)(WebExtension)?-[\d.]+\.typelib|jsc)$")
# docs/spec.md §7.2: shipped coreutils are uutils. GNU binaries carry this in --version;
# uutils' multicall binary also mentions it (in help texts), alongside its own name.
GNU_COREUTILS_MARK = b"GNU coreutils"
UUTILS_MARK = b"uutils"

FORBIDDEN_BINARIES = [
    # Shell policy (docs/spec.md §6) and root identity (§18.1, §19: run0 is the only
    # escalation); bash is base-only
    "bash", "su", "sudo", "pkexec", "doas",
    # The initrd is project-owned (§13)
    "dracut",
    # Package managers and out-of-tree module builds (§2.1)
    "rpm", "dnf", "yum", "microdnf", "zypper", "apt", "apt-get", "dpkg",
    "pacman", "emerge", "apk", "dkms",
]


def load_allowlist(path):
    allowed = set()
    if not path:
        return allowed
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if line:
                allowed.add(line.split()[0])
    return allowed


def iter_unit_files(roots):
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in sorted(filenames):
                if name.endswith(UNIT_SUFFIXES) or name.endswith(".conf") and dirpath.endswith(".d"):
                    yield os.path.join(dirpath, name)


def logical_lines(path):
    """Yield (lineno, text) with backslash continuations joined."""
    with open(path, encoding="utf-8", errors="replace") as f:
        buf, start = "", None
        for lineno, raw in enumerate(f, 1):
            line = raw.rstrip("\n")
            if start is None:
                start = lineno
            if line.endswith("\\"):
                buf += line[:-1] + " "
                continue
            yield start, buf + line
            buf, start = "", None
        if buf:
            yield start, buf


def check_units(roots, allowlist):
    problems = []
    for path in iter_unit_files(roots):
        # .wants/ links and aliases point at files scanned anyway, and an absolute
        # link inside a sysroot would resolve against the host.
        if os.path.islink(path):
            continue
        if os.path.basename(path) in allowlist:
            continue
        for lineno, line in logical_lines(path):
            m = EXEC_KEY.match(line)
            if not m:
                continue
            command = m.group(3)
            for pattern, label in SHELL_CONSTRUCTS:
                if pattern.search(command):
                    problems.append(f"{path}:{lineno}: {m.group(1)} uses {label}: {command.strip()}")
                    break
    return problems


def check_artifact(tree):
    problems = []
    for bindir in ("usr/bin", "usr/sbin", "usr/local/bin"):
        for name in FORBIDDEN_BINARIES:
            if name != "bash" and os.path.lexists(os.path.join(tree, bindir, name)):
                problems.append(f"{os.path.join(tree, bindir, name)}: must not be in any artifact")
    for dirpath, _dirnames, filenames in os.walk(tree):
        for name in filenames:
            path = os.path.join(dirpath, name)
            if WEB_ENGINE.match(name):
                problems.append(f"{path}: web engine (docs/spec.md §7.1)")
            rel = os.path.relpath(dirpath, tree)
            if rel in ("usr/bin", "usr/sbin") and not os.path.islink(path) and os.path.isfile(path):
                with open(path, "rb") as f:
                    data = f.read()
                # Only programs: scripts such as xz's xzdiff mention GNU coreutils in prose.
                if data[:4] != b"\x7fELF":
                    continue
                if GNU_COREUTILS_MARK in data and not (name == "coreutils" and UUTILS_MARK in data):
                    problems.append(f"{path}: GNU coreutils (shipped coreutils are uutils, §7.2)")
    return problems


def check_tree(sysroot):
    problems = check_artifact(sysroot)
    for bindir in ("usr/bin", "usr/sbin", "usr/local/bin"):
        for name in FORBIDDEN_BINARIES:
            candidate = os.path.join(sysroot, bindir, name)
            if os.path.lexists(candidate):
                problems.append(f"{candidate}: must not be in the base")

    sh = os.path.join(sysroot, "usr/bin/sh")
    if not os.path.lexists(sh):
        problems.append(f"{sh}: missing (base must provide a POSIX /bin/sh)")
    elif not (os.path.islink(sh) and os.path.basename(os.readlink(sh)) == "dash"):
        target = os.readlink(sh) if os.path.islink(sh) else "a regular file"
        problems.append(f"{sh}: must be a symlink to dash, found {target}")

    bin_link = os.path.join(sysroot, "bin")
    if os.path.lexists(bin_link) and not (os.path.islink(bin_link) and os.readlink(bin_link) == "usr/bin"):
        problems.append(f"{bin_link}: must be a symlink to usr/bin")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--units", nargs="+", default=[], metavar="DIR", help="unit directories to scan")
    parser.add_argument("--tree", metavar="SYSROOT", help="composed root filesystem to check")
    parser.add_argument("--artifact", nargs="+", default=[], metavar="TREE",
                        help="other final artifact trees (extensions) to check")
    parser.add_argument("--allowlist", metavar="FILE", help="unit file names exempt from the shell rule")
    args = parser.parse_args()

    if not args.units and not args.tree and not args.artifact:
        parser.error("nothing to check: pass --units, --tree and/or --artifact")

    problems = []
    if args.units:
        problems += check_units(args.units, load_allowlist(args.allowlist))
    if args.tree:
        problems += check_tree(args.tree)
    for tree in args.artifact:
        problems += check_artifact(tree)

    for problem in problems:
        print(f"policy: {problem}", file=sys.stderr)
    if problems:
        print(f"policy: {len(problems)} violation(s)", file=sys.stderr)
        return 1
    print("policy: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
