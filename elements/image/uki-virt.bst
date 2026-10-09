# SPDX-License-Identifier: MIT

kind: script
description: |
  The boot partitions' contents (docs/spec.md §13, §15, §20): unified kernel images
  (kernel + initrd + command line + os-release + systemd-stub) for XBOOTLDR, and
  systemd-boot for the ESP. Kernel compilation and UKI generation are separate stages
  (§13). Three UKIs share the kernel and initrd:
    xbootldr/EFI/Linux/beamline_<snapshot>.efi      production
    xbootldr/EFI/Linux/beamline-dev_<snapshot>.efi  development: SELinux permissive (§13)
    xbootldr/EFI/Linux/beamline-recovery.efi        the RecoveryOS stub (§20)
  Every image is signed with the development Secure Boot key (docs/security.md §19.4), and
  the signatures are verified here.

build-depends:
- junctions/freedesktop-sdk.bst:public-stacks/runtime-gnu.bst
- junctions/freedesktop-sdk.bst:components/systemd.bst
- junctions/freedesktop-sdk.bst:components/systemd-ukify.bst
- junctions/freedesktop-sdk.bst:components/sbsigntools-maybe.bst
- security/keys-uki.bst
- filename: kernel/linux-virt.bst
  config:
    location: /kernel
- filename: image/initrd-virt.bst
  config:
    location: /initrd
- filename: base/os-release.bst
  config:
    location: /os-release
- filename: image/system-virt.bst
  config:
    location: /system

variables:
  uki-keys: '%{datadir}/%{os-id}/keys/uki'
  uki-dir: '%{install-root}/xbootldr/EFI/Linux'
  # SYSTEM, read-only EROFS under dm-verity (docs/spec.md §13, §14): the commands prepend
  # roothash=, from which the initrd derives the data and hash partitions' UUIDs and sets up
  # /dev/mapper/root (docs/decisions.md D47). An appliance has no interactive first-boot
  # setup: root stays locked (§18.1) and settings come from the image or from credentials.
  # Extension images' signatures are checked by the kernel only; systemd's userspace
  # fallback is off (docs/decisions.md D53).
  kernel-cmdline: >-
    rootfstype=erofs ro
    console=%{serial-console}
    systemd.show_status=yes
    systemd.firstboot=no
    systemd.allow_userspace_verity=0
  # The development UKI differs only by its command line: SELinux permissive (§13,
  # docs/security.md §19.4).
  kernel-cmdline-dev: enforcing=0
  # The RecoveryOS stub boots the same kernel and initrd into beamline-recovery-stub.target,
  # which reports itself and powers off (docs/decisions.md D48). It mounts nothing: without
  # roothash=, the gpt-auto generator would otherwise try to activate a SYSTEM slot.
  kernel-cmdline-recovery: >-
    rd.systemd.unit=beamline-recovery-stub.target
    rd.systemd.gpt_auto=0
    console=%{serial-console}
    systemd.show_status=yes

config:
  commands:
  - |
    install -d /work "%{uki-dir}" "%{install-root}/esp/EFI/BOOT" "%{install-root}/esp/loader"
    python3 - /os-release%{indep-libdir}/os-release /work <<'EOF'
    import sys
    base = open(sys.argv[1]).read()
    def variant(name, pretty, image_id):
        lines = [l for l in base.splitlines() if not l.startswith(("PRETTY_NAME=", "IMAGE_ID="))]
        lines += [f'PRETTY_NAME="{pretty}"', f"IMAGE_ID={image_id}"]
        open(f"{sys.argv[2]}/{name}", "w").write("\n".join(lines) + "\n")
    fields = dict(l.split("=", 1) for l in base.splitlines() if "=" in l)
    pretty = fields["PRETTY_NAME"].strip('"')
    variant("os-release", pretty, "%{os-id}")
    variant("os-release-dev", pretty + ", SELinux permissive", "%{os-id}-dev")
    variant("os-release-recovery", fields["NAME"].strip('"') + " RecoveryOS (stub)", "%{os-id}-recovery")
    EOF

  - |
    kver="$(ls /kernel/usr/lib/modules)"
    roothash="$(python3 -c 'import json, sys
    print(next(p["roothash"] for p in json.load(open(sys.argv[1])) if p.get("roothash") not in (None, "", "-")))' /system/system.json)"
    uki() {
      output="$1"; osrelease="$2"; cmdline="$3"
      ukify build \
        --linux "/kernel/usr/lib/modules/${kver}/vmlinuz" \
        --initrd /initrd/initrd \
        --os-release "@${osrelease}" \
        --uname "${kver}" \
        --cmdline "${cmdline}" \
        --stub "/usr/lib/systemd/boot/efi/linux%{efi-arch}.efi.stub" \
        --signtool systemd-sbsign --sign-kernel \
        --secureboot-private-key "%{uki-keys}/db.key" \
        --secureboot-certificate "%{uki-keys}/db.crt" \
        --output "%{uki-dir}/${output}"
    }
    uki "%{os-id}_%{snapshot-id}.efi" /work/os-release \
      "roothash=${roothash} %{kernel-cmdline}"
    uki "%{os-id}-dev_%{snapshot-id}.efi" /work/os-release-dev \
      "roothash=${roothash} %{kernel-cmdline} %{kernel-cmdline-dev}"
    uki "%{os-id}-recovery.efi" /work/os-release-recovery "%{kernel-cmdline-recovery}"

  - |
    boot_name="BOOT$(echo "%{efi-arch}" | tr '[:lower:]' '[:upper:]').EFI"
    /usr/lib/systemd/systemd-sbsign sign \
      --private-key "%{uki-keys}/db.key" --certificate "%{uki-keys}/db.crt" \
      --output "%{install-root}/esp/EFI/BOOT/${boot_name}" \
      "/usr/lib/systemd/boot/efi/systemd-boot%{efi-arch}.efi"
    chmod 0644 "%{install-root}/esp/EFI/BOOT/${boot_name}" "%{uki-dir}"/*.efi
    # The newest production UKI is the default; the development and recovery entries are
    # picked from the menu (or bootctl set-oneshot).
    printf 'timeout 0\nconsole-mode keep\ndefault %{os-id}_*\n' > "%{install-root}/esp/loader/loader.conf"

  - |
    # systemd-sbsign cannot verify; sbsigntools can. Every image must carry a signature
    # that the development certificate validates.
    for efi in "%{uki-dir}"/*.efi "%{install-root}"/esp/EFI/BOOT/*.EFI; do
      sbverify --cert "%{uki-keys}/db.crt" "${efi}"
    done
