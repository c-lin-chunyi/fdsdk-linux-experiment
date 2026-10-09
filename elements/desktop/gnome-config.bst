# SPDX-License-Identifier: MIT

kind: import
description: |
  desktop-gnome configuration (docs/decisions.md D38, D54): GDM's settings (no automatic
  login: homed needs the password), gbm's GDM login stacks with pam_selinux added, the
  display-manager alias and the desktop presets. Its /etc part ships in the desktop-gnome confext.
  Depending on gdm stages this element after it, so its files replace gdm's.

depends:
- junctions/gnome-build-meta.bst:core/gdm.bst

public:
  bst:
    overlap-whitelist:
    - '%{sysconfdir}/gdm/custom.conf'
    - '%{sysconfdir}/pam.d/gdm-autologin'
    - '%{sysconfdir}/pam.d/gdm-password'

sources:
- kind: local
  path: files/desktop/gnome
