#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Static policy checks for MyOS trees and unit files (docs/spec.md §2.1, §6, §18.1).

  --units DIR...   Reject shell constructs in Exec*= lines of unit files.
  --tree SYSROOT   Reject bash, su/sudo, package managers and a non-dash /usr/bin/sh.

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

FORBIDDEN_BINARIES = [
    # Shell policy (docs/spec.md §6) and root identity (§18.1)
    "bash", "su", "sudo",
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


def check_tree(sysroot):
    problems = []
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
    parser.add_argument("--allowlist", metavar="FILE", help="unit file names exempt from the shell rule")
    args = parser.parse_args()

    if not args.units and not args.tree:
        parser.error("nothing to check: pass --units and/or --tree")

    problems = []
    if args.units:
        problems += check_units(args.units, load_allowlist(args.allowlist))
    if args.tree:
        problems += check_tree(args.tree)

    for problem in problems:
        print(f"policy: {problem}", file=sys.stderr)
    if problems:
        print(f"policy: {len(problems)} violation(s)", file=sys.stderr)
        return 1
    print("policy: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
