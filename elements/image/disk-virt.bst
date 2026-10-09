# SPDX-License-Identifier: MIT

kind: script
description: |
  Bootable GPT disk image for the Virt profile, built offline by systemd-repart (no loop
  devices, no privileges), in the 0.0.3 layout (docs/spec.md §15, docs/decisions.md D48):
  ESP (systemd-boot), XBOOTLDR (the UKIs), SYSTEM-A and SYSTEM-B with their verity slots,
  RECOVERY and RECOVERY-VERITY (reserved), and DATA. SYSTEM-A and its verity hash tree are
  image/system-virt.bst's split images, copied in block for block; the extension images go
  to DATA. Output: disk.raw.

build-depends:
- junctions/freedesktop-sdk.bst:public-stacks/runtime-gnu.bst
- junctions/freedesktop-sdk.bst:components/systemd.bst
- junctions/freedesktop-sdk.bst:components/python3.bst
- junctions/freedesktop-sdk.bst:components/dosfstools.bst
- junctions/freedesktop-sdk.bst:components/e2fsprogs.bst
- junctions/freedesktop-sdk.bst:components/mtools.bst
- image/repart-virt.bst
- filename: image/system-virt.bst
  config:
    location: /system
- filename: image/uki-virt.bst
  config:
    location: /work/src
- filename: extensions/admin.bst
  config:
    location: /extensions
- filename: extensions/desktop-gnome.bst
  config:
    location: /extensions

variables:
  # Fixed seed: partition and filesystem UUIDs are derived from it, keeping the image
  # reproducible. SYSTEM-A's UUIDs come from its root hash instead (drop-ins below).
  disk-seed: 6b0d7e6e-3f0a-4a51-9a3c-7f2b8c1e5d40

environment:
  E2FSPROGS_FAKE_TIME: '%{source-date-epoch}'
  SOURCE_DATE_EPOCH: '%{source-date-epoch}'
  TMPDIR: /work/tmp

config:
  commands:
  - |
    # Extension images go to DATA (docs/spec.md §8), one set per snapshot, under the names
    # the units link by IMAGE_VERSION (docs/decisions.md D50): desktop-gnome is linked at boot
    # (beamline-extensions-link.service), admin on demand (beamline-admin.service).
    seed=/work/src/data-seed
    install -d "${seed}/var/lib/beamline/extensions" "${seed}/var/lib/beamline/confexts"
    for name in admin desktop-gnome; do
      install -m644 "/extensions/${name}.sysext.raw" \
        "${seed}/var/lib/beamline/extensions/${name}_%{snapshot-id}.raw"
      install -m644 "/extensions/${name}.confext.raw" \
        "${seed}/var/lib/beamline/confexts/${name}_%{snapshot-id}.raw"
    done

  - |
    # The split SYSTEM images keep the UUIDs repart derived from their root hash: the UKI's
    # roothash= finds them by those UUIDs (docs/decisions.md D47). Both carry the label
    # systemd-sysupdate gives an installed slot, <os-id>_<snapshot> (D48).
    cp -r "%{datadir}/%{os-id}/repart/virt" /work/definitions
    python3 - /system/system.json /work/definitions "%{os-id}_%{snapshot-id}" <<'EOF'
    import json, os, sys
    partitions = json.load(open(sys.argv[1]))
    def uuid(verity):
        found = [p["uuid"] for p in partitions
                 if p["type"].startswith("root-") and p["type"].endswith("-verity") == verity]
        assert len(found) == 1, (verity, partitions)
        return found[0]
    for name, verity in (("20-system-a.conf", False), ("21-system-a-verity.conf", True)):
        dropin = os.path.join(sys.argv[2], name + ".d")
        os.makedirs(dropin)
        with open(os.path.join(dropin, "uuid.conf"), "w") as f:
            f.write(f"[Partition]\nUUID={uuid(verity)}\nLabel={sys.argv[3]}\n")
        print(name, uuid(verity))
    EOF

  - |
    mkdir -p "${TMPDIR}"
    systemd-repart \
      --offline=yes \
      --dry-run=no \
      --empty=create \
      --size=auto \
      --seed=%{disk-seed} \
      --definitions=/work/definitions \
      --copy-source=/work/src \
      "%{install-root}/disk.raw"
