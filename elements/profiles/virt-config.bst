# SPDX-License-Identifier: MIT

kind: import
description: Virt profile configuration (systemd-networkd, docs/spec.md §10.2).

sources:
- kind: local
  path: files/network/networkd
  directory: usr/lib/systemd/network
