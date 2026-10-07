# SPDX-License-Identifier: MIT

kind: import
description: systemd-repart definitions for the Virt disk image (docs/spec.md §15).

config:
  target: '%{datadir}/%{os-id}/repart/virt'

sources:
- kind: local
  path: files/repart/virt
