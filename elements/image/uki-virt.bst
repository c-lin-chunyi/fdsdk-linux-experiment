# SPDX-License-Identifier: MIT

kind: script
description: |
  Unified kernel image (kernel + initrd + command line + os-release + systemd-stub)
  and systemd-boot, laid out as the ESP contents. Kernel compilation and UKI
  generation are separate stages (docs/spec.md §13).

build-depends:
- junctions/freedesktop-sdk.bst:public-stacks/runtime-gnu.bst
- junctions/freedesktop-sdk.bst:components/systemd.bst
- junctions/freedesktop-sdk.bst:components/systemd-ukify.bst
- filename: kernel/linux-virt.bst
  config:
    location: /kernel
- filename: image/initrd-virt.bst
  config:
    location: /initrd
- filename: base/os-release.bst
  config:
    location: /os-release

variables:
  # 0.0.1 bring-up root (docs/decisions.md D5); dm-verity discovery replaces this.
  # An appliance has no interactive first-boot setup: root stays locked (§18.1) and
  # settings come from the image or from credentials.
  kernel-cmdline: >-
    root=PARTLABEL=root rootfstype=ext4 rw
    console=%{serial-console}
    systemd.show_status=yes
    systemd.firstboot=no

config:
  commands:
  - |
    kver="$(ls /kernel/usr/lib/modules)"
    install -d "%{install-root}/EFI/Linux" "%{install-root}/EFI/BOOT" "%{install-root}/loader"
    ukify build \
      --linux "/kernel/usr/lib/modules/${kver}/vmlinuz" \
      --initrd /initrd/initrd \
      --os-release @/os-release/usr/lib/os-release \
      --uname "${kver}" \
      --cmdline "%{kernel-cmdline}" \
      --stub "/usr/lib/systemd/boot/efi/linux%{efi-arch}.efi.stub" \
      --output "%{install-root}/EFI/Linux/%{os-id}_%{os-version}.efi"
  - |
    boot_name="BOOT$(echo "%{efi-arch}" | tr '[:lower:]' '[:upper:]').EFI"
    install -m644 "/usr/lib/systemd/boot/efi/systemd-boot%{efi-arch}.efi" "%{install-root}/EFI/BOOT/${boot_name}"
    printf 'timeout 0\nconsole-mode keep\n' > "%{install-root}/loader/loader.conf"
