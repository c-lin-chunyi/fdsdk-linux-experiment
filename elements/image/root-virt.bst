# SPDX-License-Identifier: MIT

kind: script
description: |
  Finalised Virt root: integration toolbox removed, root-identity policy applied, presets
  applied, no machine-id (so the first boot is a real first boot). Tools run from the build sandbox; the OS tree is
  only data at /sysroot.

build-depends:
- junctions/freedesktop-sdk.bst:public-stacks/runtime-gnu.bst
- junctions/freedesktop-sdk.bst:components/findutils.bst
- junctions/freedesktop-sdk.bst:components/systemd.bst
- filename: image/root-virt-tree.bst
  config:
    location: /sysroot
# Reference trees used to compute exactly which files the toolbox added.
- filename: image/integration-tools.bst
  config:
    location: /reference/tools
- filename: profiles/virt.bst
  config:
    location: /reference/os

config:
  commands:
  - |
    mkdir -p /work
    (cd /reference/tools && find . -mindepth 1 ! -type d | sort) > /work/tools-files
    (cd /reference/os && find . -mindepth 1 ! -type d | sort) > /work/os-files
    (cd /reference/tools && find . -mindepth 1 -type d | sort) > /work/tools-dirs
    (cd /reference/os && find . -mindepth 1 -type d | sort) > /work/os-dirs
    comm -23 /work/tools-files /work/os-files > /work/remove-files
    comm -23 /work/tools-dirs /work/os-dirs | sort -r > /work/remove-dirs
    while IFS= read -r path; do rm -f "/sysroot/${path#./}"; done < /work/remove-files
    while IFS= read -r path; do rmdir "/sysroot/${path#./}" 2>/dev/null || true; done < /work/remove-dirs
    echo "Removed $(wc -l < /work/remove-files) integration toolbox files"

  - |
    # docs/spec.md §18.1: su is absent. util-linux ships it and systemd depends on
    # util-linux, so it is removed here rather than by forking FDSDK's recipe.
    rm -f /sysroot/usr/bin/su /sysroot/etc/pam.d/su /sysroot/etc/pam.d/su-l

  - systemctl --root=/sysroot preset-all
  - rm -f /sysroot/etc/machine-id
  - cp -a /sysroot/. "%{install-root}/"
