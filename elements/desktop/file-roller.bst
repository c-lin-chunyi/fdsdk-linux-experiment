# SPDX-License-Identifier: MIT

kind: meson
description: |
  File Roller, GNOME's archive manager (docs/spec.md §7.1). Not in gnome-build-meta, so
  project-owned; built against gbm's GTK 4 and libadwaita, with Nautilus' context-menu
  actions and without PackageKit.

build-depends:
- junctions/freedesktop-sdk.bst:public-stacks/buildsystem-meson.bst
- junctions/freedesktop-sdk.bst:components/itstool.bst
- junctions/freedesktop-sdk.bst:components/desktop-file-utils.bst

depends:
- junctions/gnome-build-meta.bst:sdk/gtk.bst
- junctions/gnome-build-meta.bst:sdk/libadwaita.bst
- junctions/gnome-build-meta.bst:sdk/json-glib.bst
- junctions/gnome-build-meta.bst:core/nautilus.bst
- junctions/freedesktop-sdk.bst:components/libarchive.bst

variables:
  meson-local: >-
    -Dpackagekit=false
    -Dnautilus-actions=enabled

sources:
- kind: git
  url: gnome:file-roller.git
  track: master
  ref-format: git-describe
