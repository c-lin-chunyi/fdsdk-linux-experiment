# SPDX-License-Identifier: MIT

kind: script
description: |
  Bootable GPT disk image for the Virt profile, built offline by systemd-repart
  (no loop devices, no privileges). Output: disk.raw.

build-depends:
- junctions/freedesktop-sdk.bst:public-stacks/runtime-gnu.bst
- junctions/freedesktop-sdk.bst:components/systemd.bst
- junctions/freedesktop-sdk.bst:components/dosfstools.bst
- junctions/freedesktop-sdk.bst:components/e2fsprogs.bst
- junctions/freedesktop-sdk.bst:components/mtools.bst
- image/repart-virt.bst
- filename: image/root-virt.bst
  config:
    location: /sysroot
- filename: image/uki-virt.bst
  config:
    location: /sysroot/efi

variables:
  # Fixed seed: partition and filesystem UUIDs are derived from it, keeping the
  # image reproducible.
  disk-seed: 6b0d7e6e-3f0a-4a51-9a3c-7f2b8c1e5d40

environment:
  E2FSPROGS_FAKE_TIME: '%{source-date-epoch}'
  TMPDIR: /work/tmp

config:
  commands:
  - |
    mkdir -p "${TMPDIR}"
    systemd-repart \
      --offline=yes \
      --dry-run=no \
      --empty=create \
      --size=auto \
      --seed=%{disk-seed} \
      --definitions="%{datadir}/%{os-id}/repart/virt" \
      --copy-source=/sysroot \
      "%{install-root}/disk.raw"
