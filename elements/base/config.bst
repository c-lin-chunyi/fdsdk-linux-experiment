# SPDX-License-Identifier: MIT

kind: import
description: |
  Project-owned base configuration: units, presets, sysusers.d, tmpfiles.d and the
  few /etc files the OS needs before confext exists (docs/spec.md §14).

sources:
- kind: local
  path: files/base/systemd
  directory: usr/lib/systemd
- kind: local
  path: files/base/sysusers.d
  directory: usr/lib/sysusers.d
- kind: local
  path: files/base/tmpfiles.d
  directory: usr/lib/tmpfiles.d
- kind: local
  path: files/base/etc
  directory: etc
