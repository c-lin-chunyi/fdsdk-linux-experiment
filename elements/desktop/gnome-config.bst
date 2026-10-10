# SPDX-License-Identifier: MIT

kind: import
description: |
  desktop-gnome configuration (docs/decisions.md D38, D54): GDM's settings (no automatic
  login: homed needs the password), gbm's GDM login stacks with pam_selinux added, the
  display-manager alias and the desktop presets, and cupsd's ServerRoot on DATA (D58). Its /etc
  part ships in the desktop-gnome confext. Depending on gdm and cups-daemon stages this element
  after them, so its files replace theirs.

depends:
- junctions/gnome-build-meta.bst:core/gdm.bst
- junctions/freedesktop-sdk.bst:components/cups-daemon.bst

public:
  bst:
    overlap-whitelist:
    - '%{sysconfdir}/gdm/custom.conf'
    - '%{sysconfdir}/pam.d/gdm-autologin'
    - '%{sysconfdir}/pam.d/gdm-password'
    - '%{sysconfdir}/cups/cups-files.conf'

sources:
- kind: local
  path: files/desktop/gnome
