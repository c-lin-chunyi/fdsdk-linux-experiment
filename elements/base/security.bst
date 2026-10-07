# SPDX-License-Identifier: MIT

kind: stack
description: |
  Authentication and trust infrastructure: PAM with its base configuration and the
  CA bundle. polkit joins when the first narrow privileged service lands
  (docs/spec.md §19).

depends:
- junctions/freedesktop-sdk.bst:components/linux-pam.bst
- junctions/freedesktop-sdk.bst:components/ca-certificates.bst
