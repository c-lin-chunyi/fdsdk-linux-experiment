# SPDX-License-Identifier: MIT

kind: import
description: Policy checker and its allowlist, staged into test sandboxes.

config:
  target: '%{libexecdir}/%{os-id}-tests'

sources:
- kind: local
  path: tools/check-policy.py
- kind: local
  path: policy/unit-shell-allowlist.txt
