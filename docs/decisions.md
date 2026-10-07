# Decisions

Deliberate choices, interpretations of, and deviations from [spec.md](spec.md).
Newest last. Each entry: what, why, and when to revisit.

## D1. Pin Freedesktop SDK 26.08.2 and BuildStream 2.8.1

FDSDK `freedesktop-sdk-26.08.2` (commit `32c5fea7`, 2026-09-28) is the known-good
substrate (§35). BuildStream 2.8.1 and buildbox come from Fedora 44 packages in the
builder. The plugin junctions use the same plugin versions FDSDK 26.08.2 uses
(`buildstream-plugins` 2.8.0, `buildstream-plugins-community` 2.3.3).

Revisit: on each FDSDK point release (a focused update change of its own).

## D2. Builder VM: Lima + Fedora 44

§23 allows Lima or Tart. Lima is already installed on the development host, has a
Fedora 44 image, and supports `nestedVirtualization` on M3+/macOS 15+ for §24.2. Fedora
packages BuildStream 2 and buildbox, so the same `ci/bootstrap` serves the VM and a
`fedora:44` container on hosted runners.

## D3. Kernel source channels are include files, not elements

§34 lists `elements/kernel/linux-{release,rc,main}.bst`. A BuildStream source cannot be
shared between elements, and staging a Linux tree as an artifact would be wasteful, so each
channel is `include/kernel/<channel>.yml` (the `sources:` pin), and profile kernels
(`linux-virt.bst`, later `linux-hardware.bst`) include one channel plus
`include/kernel/build.yml`. Only `release.yml` exists for 0.0.1.

## D4. Release-channel kernels come from cdn.kernel.org tarballs

Release tarballs are immutable and far cheaper to fetch than a full `linux.git` mirror.
The rc and main channels (0.1) will use git refs, as §2.3 shows.

## D5. 0.0.1 disk layout is ESP + ext4 ROOT, mounted read-write

§15 lists `ESP, ROOT, VAR` as the bootstrap layout. A separate VAR only does something with
a read-only root, and systemd's automatic `/var` discovery needs partition UUIDs derived
from the machine ID, which pairs naturally with the immutable root. So 0.0.1 boots a
read-write ext4 root (found with `root=PARTLABEL=root`), and VAR arrives together with
the EROFS root in 0.0.2 (§37). The image artifact itself is still never modified: tests
boot a qcow2 overlay.

## D6. initrd: systemd-native, built from the root tree

§36 requires a systemd-based initrd. `image/initrd-virt.bst` builds it the way
mkosi-initrd does: a trimmed copy of the finished Virt root (no kernel modules, locales or
docs) plus `/etc/initrd-release`, `/init -> systemd`, and a user database created at build
time with `systemd-sysusers --root`. It is packed as a zstd cpio (about 39 MB). systemd
runs `initrd.target`, mounts `root=` and switches root.

dracut-ng (shipped by FDSDK) was tried first and dropped. In `--sysroot` mode it expects its
own module tree and coreutils inside the target. It picks the build sandbox's bash as the
initrd shell. It exits 0 without writing an initrd when it is unhappy. And its initrd is
built around shell hooks, which runs against §6.

The host's enablement symlinks are removed from the initrd copy: unit start-rate
counters survive switch-root, so a service failing in the initrd is refused in the host.

## D7. Boot marker printed by `systemd-escape`

§29 asks for a `MYOS_BOOT_OK` serial marker. The base has no `echo`/`cat` (FDSDK 26.08
runtime-minimal has no coreutils) and §6 bans shell in base units. `myos-boot-ok.service`
runs `systemd-escape MYOS_BOOT_OK` (which prints its argument unchanged) with
`StandardOutput=journal+console` after `multi-user.target`.

## D8. Development credentials only at boot

The prototype `dev` account (§18.3) is defined in `sysusers.d` with no password. The QEMU
harness passes `passwd.plaintext-password.dev` as a systemd credential over SMBIOS type 11
in `--interactive` mode only. Root remains locked.

## D9. Extra `ci/check` script

Not in §26's list: fast static checks (unit-file shell policy, Python, YAML, shellcheck)
that run in seconds on macOS without the builder, first in `ci/test-all`.

## D10. Identity variables

`os-id`, `os-name` and `os-version` in `project.conf` feed `os-release`, kernel build
metadata, artifact and UKI names. The literal name also appears in: the boot marker
(`MYOS_BOOT_OK`, `myos-boot-ok.service`, `tools/qemu-test.py` default), kernel
`CONFIG_LOCALVERSION` (`files/kernel/config/*.config`), `80-myos.preset`, and the Lima
instance name `myos-builder`.

## D11. Per-architecture kernel fragments

§11.3 describes `common.config` feeding profile fragments. Some settings are
architecture-specific, so the merge order is
`defconfig + common.config + arch-<kernel-arch>.config + <profile>.config`.
The first entry: `CONFIG_COMPAT` is off on arm64. MyOS has no AArch32 userspace, and FDSDK's
LLVM is built without the 32-bit ARM target, so clang cannot build the compat vDSO.

## D12. Integration commands run with a temporary toolbox

FDSDK integration commands (`update-ca-trust`, the cracklib dictionary) assume coreutils
and gzip, which the base deliberately lacks. `image/root-virt-tree.bst` composes the profile
together with `image/integration-tools.bst` (FDSDK `bootstrap/coreutils` and
`bootstrap/gzip`, chosen because their runtime closures carry no bash), so integration
succeeds. `image/root-virt.bst` then deletes exactly the files the toolbox added, computed
from reference stagings of the toolbox and of the profile.

## D13. Image-assembly policy fixes

Applied in project-owned image composition rather than by forking FDSDK recipes:
- `su` and its PAM files are removed (§18.1). util-linux ships it and systemd depends on
  util-linux. `tools/check-policy.py` rejects `su` and `sudo`.
- `auditd`/`audit-rules` are preset-disabled: not part of §5.2, and they failed at boot.
- `systemd.firstboot=no` on the kernel command line: an appliance has no interactive
  first-boot setup, and root stays locked.
- `bootstrap/acl.bst` is added to the base: systemd `dlopen()`s libacl for journal and
  `/run` ACLs, but FDSDK's systemd element does not declare it.
- A `systemd-sysusers.service` drop-in imports the `passwd.*.dev` credentials (upstream only
  imports root's), so D8 works.

## D14. Junction refs live in `junction.refs`

With `ref-storage: project.refs`, BuildStream reads junction refs from `junction.refs` in
its first loading pass (plugins, includes from junctions), before `project.refs`. That is
why §34 lists both files.
