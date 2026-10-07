# SPDX-License-Identifier: MIT

kind: stack
description: |
  systemd (init, udev, journald, logind, networkd, resolved, timesyncd, repart,
  sysext, ...) and kmod. Version follows FDSDK until an override is needed
  (docs/spec.md §2.2: source-ref override first, element override second).

depends:
- junctions/freedesktop-sdk.bst:components/systemd.bst
- junctions/freedesktop-sdk.bst:components/kmod.bst
# systemd dlopen()s libacl (journal and /run ACLs); FDSDK does not declare it.
- junctions/freedesktop-sdk.bst:bootstrap/acl.bst
