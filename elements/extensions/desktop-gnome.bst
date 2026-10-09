# SPDX-License-Identifier: MIT

kind: script
description: |
  The desktop-gnome system extension and confext images (docs/spec.md §7.1, §8;
  docs/decisions.md D38), merged automatically from DATA. Unit enablement comes from
  presets applied at build time.

(@):
- include/extension.yml

build-depends:
- junctions/freedesktop-sdk.bst:public-stacks/runtime-gnu.bst
- junctions/freedesktop-sdk.bst:components/python3.bst
- junctions/freedesktop-sdk.bst:components/erofs-utils.bst
- image/repart-extension.bst
- security/keys-verity.bst
- junctions/freedesktop-sdk.bst:components/systemd.bst
- image/image-tools.bst
- image/permissions.bst
- filename: extensions/desktop-gnome-tree.bst
  config:
    location: /tree
- filename: image/root-virt.bst
  config:
    location: /base
- filename: desktop/gnome.bst
  config:
    location: /reference/content
- filename: image/integration-tools.bst
  config:
    location: /reference/tools

variables:
  extension-name: desktop-gnome
  extension-presets: 'true'
