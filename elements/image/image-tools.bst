# SPDX-License-Identifier: MIT

kind: import
description: |
  Image-building helpers staged into image elements: the extension composer and the
  artifact policy checker (docs/decisions.md D36).

config:
  target: '%{libexecdir}/%{os-id}-image-tools'

sources:
- kind: local
  path: tools/build-extension.py
- kind: local
  path: tools/check-policy.py
