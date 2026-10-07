# SPDX-License-Identifier: MIT

kind: script
description: |
  systemd-native initrd (docs/spec.md §13, §36), built the way mkosi-initrd does it: a
  trimmed copy of the Virt root plus /etc/initrd-release, packed as a zstd cpio. systemd
  runs initrd.target, mounts root= and switches root; no dracut hooks or shell scripts.
  The Virt kernel has its boot path built in, so no kernel modules are included.

build-depends:
- junctions/freedesktop-sdk.bst:public-stacks/runtime-gnu.bst
- junctions/freedesktop-sdk.bst:components/cpio.bst
- junctions/freedesktop-sdk.bst:components/findutils.bst
- junctions/freedesktop-sdk.bst:components/systemd.bst
- junctions/freedesktop-sdk.bst:components/zstd.bst
- filename: image/root-virt.bst
  config:
    location: /sysroot

config:
  commands:
  - |
    tree=/work/initrd
    mkdir -p /work
    cp -a /sysroot "${tree}"

    # Not needed to find and mount the root filesystem.
    rm -rf "${tree}"/usr/lib/modules/*/kernel \
           "${tree}"/usr/lib/modules/*/vmlinuz \
           "${tree}"/usr/share/locale \
           "${tree}"/usr/share/i18n \
           "${tree}"/usr/share/doc \
           "${tree}"/usr/share/man \
           "${tree}"/usr/share/info \
           "${tree}"/usr/share/licenses

    # The host's enablement symlinks (networkd, resolved, ...) are not for the initrd;
    # initrd.target pulls in what the initrd needs. Unit start-rate counters survive
    # switch-root, so services failing here would also be refused in the host.
    rm -rf "${tree}/etc/systemd/system"

    # The initrd has no first boot of its own: give it a complete user database now.
    systemd-sysusers --root="${tree}"
    # sysusers writes mode 0000; the unprivileged build sandbox must still read them to pack.
    chmod 0400 "${tree}/etc/shadow" "${tree}/etc/gshadow"

    # systemd recognises an initrd by /etc/initrd-release and starts from /init.
    rm -f "${tree}/etc/initrd-release"
    cp "${tree}/usr/lib/os-release" "${tree}/etc/initrd-release"
    ln -sf usr/lib/systemd/systemd "${tree}/init"

  - |
    cd /work/initrd
    find . -mindepth 1 | LC_ALL=C sort \
      | cpio --quiet --reproducible -o -H newc \
      | zstd -q -19 -T0 > "%{install-root}/initrd"
    test -s "%{install-root}/initrd"
    du -h "%{install-root}/initrd"
