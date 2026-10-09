# SPDX-License-Identifier: MIT

kind: compose
description: |
  The Virt base and the admin extension content, composed and integrated together, as
  image/root-virt-tree.bst does for the root. extensions/admin.bst subtracts the base.
  FDSDK's integration commands run on uutils here, so of the integration toolbox only
  gzip is needed; GNU coreutils would collide with uutils.

build-depends:
- profiles/virt.bst
- junctions/freedesktop-sdk.bst:bootstrap/gzip.bst
- admin/admin.bst

config:
  exclude:
  - debug
  - devel
  - doc
  - tests
  include-orphans: true
