# SPDX-License-Identifier: MIT

kind: script
description: |
  Static policy test of the finished Virt root (docs/spec.md §6, §2.1): no bash, sh is
  dash, no package managers, no shell constructs in unit Exec lines. Runs inside
  BuildStream so local and hosted CI enforce it identically.

build-depends:
- junctions/freedesktop-sdk.bst:public-stacks/runtime-gnu.bst
- junctions/freedesktop-sdk.bst:components/python3.bst
- tests/policy-tools.bst
- filename: image/root-virt.bst
  config:
    location: /sysroot

config:
  commands:
  - |
    python3 "%{libexecdir}/%{os-id}-tests/check-policy.py" \
      --tree /sysroot \
      --units /sysroot/usr/lib/systemd/system /sysroot/etc/systemd/system \
      --allowlist "%{libexecdir}/%{os-id}-tests/unit-shell-allowlist.txt"
