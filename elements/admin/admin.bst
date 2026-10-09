# SPDX-License-Identifier: MIT

kind: stack
description: |
  Content of the admin system extension (docs/spec.md §7.2): interactive maintenance tools
  absent from the base, activated on demand. Coreutils are uutils. ethtool, tcpdump and
  lsof (not in FDSDK) are later additions.

depends:
- admin/uutils-coreutils.bst
- admin/bash.bst
- junctions/freedesktop-sdk.bst:components/grep.bst
- junctions/freedesktop-sdk.bst:components/sed.bst
- junctions/freedesktop-sdk.bst:components/gawk.bst
- junctions/freedesktop-sdk.bst:components/findutils.bst
- junctions/freedesktop-sdk.bst:components/procps.bst
- junctions/freedesktop-sdk.bst:components/iproute2.bst
- junctions/freedesktop-sdk.bst:components/pciutils.bst
- junctions/freedesktop-sdk.bst:components/usbutils.bst
- junctions/freedesktop-sdk.bst:components/strace.bst
- junctions/freedesktop-sdk.bst:components/curl.bst
- junctions/freedesktop-sdk.bst:components/jq.bst
- junctions/freedesktop-sdk.bst:components/less.bst
- junctions/freedesktop-sdk.bst:components/file.bst
- junctions/freedesktop-sdk.bst:components/vim.bst
- junctions/freedesktop-sdk.bst:components/e2fsprogs.bst
- junctions/freedesktop-sdk.bst:components/dosfstools.bst
- junctions/freedesktop-sdk.bst:components/erofs-utils.bst
