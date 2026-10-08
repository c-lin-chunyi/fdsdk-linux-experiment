# Decisions

Deliberate choices, interpretations of, and deviations from [spec.md](spec.md).
Newest last. Each entry: what, why, and when to revisit. Entries overtaken by a spec revision
stay for history and are marked *Superseded*.

## D1. Pin Freedesktop SDK 26.08.2 and BuildStream 2.8.1

*FDSDK part superseded by spec rev 2 (§2.2, §31): FDSDK is now tracked at `master`. The
BuildStream, buildbox and plugin pins remain, as Layer 0 (§31.3).*

FDSDK `freedesktop-sdk-26.08.2` (commit `32c5fea7`, 2026-09-28) is the known-good
substrate (§35). BuildStream 2.8.1 and buildbox come from Fedora 44 packages in the
builder. The plugin junctions use the same plugin versions FDSDK 26.08.2 uses
(`buildstream-plugins` 2.8.0, `buildstream-plugins-community` 2.3.3).

Revisit (Layer 0 only): deliberately, never as part of an integration cycle.

## D2. Builder VM: Lima + Fedora 44

§23 allows Lima or Tart. Lima is already installed on the development host, has a
Fedora 44 image, and supports `nestedVirtualization` on M3+/macOS 15+ for §24.2. Fedora
packages BuildStream 2 and buildbox, so the same `ci/bootstrap` serves the VM and a
`fedora:44` container on hosted runners.

## D3. Kernel source channels are include files, not elements

*Superseded by spec rev 2 (§11.2): there is a single kernel source, Linux `master`. The idea
survives: the source pin is the include file `include/kernel/linux.yml`, shared by profile
kernels together with `include/kernel/build.yml`.*

§34 lists `elements/kernel/linux-{release,rc,main}.bst`. A BuildStream source cannot be
shared between elements, and staging a Linux tree as an artifact would be wasteful, so each
channel is `include/kernel/<channel>.yml` (the `sources:` pin), and profile kernels
(`linux-virt.bst`, later `linux-hardware.bst`) include one channel plus
`include/kernel/build.yml`. Only `release.yml` exists for 0.0.1.

## D4. Release-channel kernels come from cdn.kernel.org tarballs

*Superseded by spec rev 2 (§11.2): the kernel comes from `linux.git` `master` through
`git_repo`, which fetches shallowly (depth = commits since the nearest tag).*

Release tarballs are immutable and far cheaper to fetch than a full `linux.git` mirror.
The rc and main channels (0.1) will use git refs, as §2.3 shows.

## D5. 0.0.1 disk layout is ESP + ext4 ROOT, mounted read-write

§15 lists `ESP, ROOT, VAR` as the bootstrap layout. A separate VAR only does something with
a read-only root, and systemd's automatic `/var` discovery needs partition UUIDs derived
from the machine ID, which pairs naturally with the immutable root. So 0.0.1 boots a
read-write ext4 root (found with `root=PARTLABEL=root`), and VAR arrives together with
the EROFS root in 0.0.2 (§37). The image artifact itself is still never modified: tests
boot a qcow2 overlay. Spec rev 2 (§15) folds this into the bring-up progression: 0.0.2 brings
SYSTEM-A (EROFS) and DATA (/var, /home).

## D6. initrd: systemd-native, built from the root tree

*Made binding by spec rev 2 (§13, invariant 29): the initrd is project-owned and dracut is
not used.*

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

§29 asks for a `BEAMLINE_BOOT_OK` serial marker. The base has no `echo`/`cat` (FDSDK 26.08
runtime-minimal has no coreutils) and §6 bans shell in base units. `beamline-boot-ok.service`
runs `systemd-escape BEAMLINE_BOOT_OK` (which prints its argument unchanged) with
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
(`BEAMLINE_BOOT_OK`, `beamline-boot-ok.service`, `tools/qemu-test.py` default), kernel
`CONFIG_LOCALVERSION` (`files/kernel/config/*.config`), `80-beamline.preset`, and the Lima
instance name `myos-builder`.

## D11. Per-architecture kernel fragments

§11.3 describes `common.config` feeding profile fragments. Some settings are
architecture-specific, so the merge order is
`defconfig + common.config + arch-<kernel-arch>.config + <profile>.config`.
The first entry: `CONFIG_COMPAT` is off on arm64. Beamline has no AArch32 userspace, and FDSDK's
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

## D15. systemd `main` through one FDSDK element override

Every FDSDK systemd element (`systemd`, `systemd-libs`, `systemd-ukify`,
`systemd-kernel-install`, `systemd-manifest`) is a filter over
`components/_private/systemd-base.bst`, so the junction overrides that one element with
`elements/overrides/systemd-base.bst`. A source-ref override is not enough: tracking `main`
instead of FDSDK's `v*` tags changes the source's `track:`.

The override is a copy of FDSDK's recipe at a recorded commit (header `Copied from:`).
The documented changes are the junction-prefixed dependencies, `target_arch` becoming `arch`,
the inline `git_repo` source on `main`, and a local copy of `90-sysupdate.preset`.
`project.conf` loads the `meson` plugin with `include/meson-conf.yml`, an attributed copy
of FDSDK's `include/_private/meson-conf.yml` (including it through the junction leaves its
variables unresolved), so the override builds with FDSDK's flags. Overriding systemd changes the cache keys of
FDSDK elements that depend on it, and those rebuild locally.

Revisit: whenever FDSDK changes the original recipe (integration cycles report drift).

## D16. Snapshot mechanics

- **Id.** `YYYYMMDD.HHMM` in UTC (§17.2), written to `include/snapshot.yml` only while a cycle
  runs, and shipped as `IMAGE_VERSION`. Outside integration it is `dev`. BuildStream has no
  free-form string options, so a variables include is the way to inject it; only
  `os-release` and what is assembled from it rebuild.
- **Manifest.** Lists the source refs and commits, nearest tags, HEAD conformity, pins
  and lag. It also records the repository commit with a fingerprint of uncommitted changes,
  the Layer 0 pins and the provenance (BuildStream, buildbox, builder).
- **Published files.** `out/snapshots/<id>/`, with `latest-green.json` beside them.
  Provenance is never baked into the image, so a different runner can reproduce the same bytes.
- **Working tree.** It keeps the latest-green refs. A failed cycle restores the refs files
  from its own backup.
- **Recording.** Committing and tagging (`--commit`) is opt-in. Rebuilding a snapshot
  means: its repository commit, its refs, and `snapshot-id` set to the id.
- **SYSEXT_LEVEL.** It stays the milestone version until extensions exist (0.0.2). It will
  then follow the snapshot, because extensions are release-coupled (§8).

## D17. FDSDK selection: newest upstream-CI-green master commit

§31.1 makes FDSDK's designated selection the newest `master` commit whose upstream
pipeline succeeded, found through the GitLab API. FDSDK CI pushes artifacts for protected
branches, but superseded pipelines are cancelled. A commit without a successful pipeline
therefore usually means local builds of toolchain-level elements (hours). The manifest
records `head_at_resolution` and `lag_commits`, so any lag stays visible. A treeless mirror in
`~/.cache/beamline/mirrors/` provides the `git describe` ref and the commit counts.

## D18. dash tracks `master`

dash is project-owned only because FDSDK has no element for it. Like every project-owned
source it follows its upstream development branch (§31).

## D19. Green means no failed units

`tools/qemu-test.py` fails a boot on any systemd `[FAILED]` or `[DEPEND]` status line
before the marker, after stripping colour codes. During 0.0.1 bring-up, a boot printed
`BEAMLINE_BOOT_OK` while networkd and resolved were failing. An integration gate has to mean
"healthy".

## D20. Green snapshots are committed and tagged by default

Per spec rev 3 §17.4, `record --result green` commits `project.refs` and `junction.refs`
(`snapshot <id>`) and tags the commit `snapshot-<id>`. If the refs did not change, it only
tags `HEAD`. `--no-commit` opts out. If anything outside the refs files and
`include/snapshot.yml` is uncommitted, the snapshot is still published to `out/snapshots/`
but not recorded in git. A tag therefore always points at the history that actually
produced the snapshot. The manifest's `git` field says what happened.

## D21. Override drift fails the cycle at resolve

Per spec rev 3 §31.4, `resolve` compares each override's `Copied from:` FDSDK commit with
the selected FDSDK commit, using the treeless mirror. If the original recipe changed, the
integration is recorded as failed (`failure: override drift`) before any build starts.
The refs files are restored and `ci/integrate` exits non-zero. Verified by pointing the
systemd override's header at FDSDK 26.08.2 (integration `20261008.0600`).

## D22. homed and sysupdate preset-disabled until their milestones

`80-beamline.preset` disables `systemd-homed*` and `systemd-sysupdate*`. Upstream presets enabled
`systemd-homed.service`, `systemd-homed-activate.service`, the sysupdate notify sockets and
`systemd-sysupdate-update.timer`. Only `systemd-sysupdate.socket` (a Varlink endpoint) stays
listening, because upstream wires it statically into `sockets.target`, where presets do not
reach. It activates only on a client request and has no transfer definitions to act on.
Remove these lines when homed (after SELinux) and sysupdate (0.0.3) arrive. Verified in
snapshot `20261008.0657`.

## D23. systemd feature trim through a second override

Per spec rev 3 §5.2, `overrides/systemd-base.bst` disables AppArmor, QR codes, xkbcommon and
journal-remote/upload (`-Dremote=disabled -Dmicrohttpd=disabled`), and drops their build
dependencies. This alone would leave FDSDK's `components/systemd.bst` filter pulling
`libmicrohttpd` and `libapparmor` into the runtime closure, so it is overridden too, as
`overrides/systemd.bst`: a copy without those runtime dependencies, also checked for drift.

curl stays, because `systemd-sysupdate` downloads need it at 0.0.3. TPM2, FIDO2 and
cryptsetup stay for the security milestones. `libapparmor` remains in the image only because
FDSDK's dbus depends on it.

Verified in snapshot `20261008.0719`: no libmicrohttpd, libqrencode, libxkbcommon or
journal-remote/upload in the image.

## D24. Renamed to Beamline; builder VM keeps its name

Per spec rev 3, the OS is Beamline (`os-id: beamline`, BuildStream project `beamline`), its
reverse-DNS prefix is `org.beamline`, and its marker is `BEAMLINE_BOOT_OK`
(`beamline-boot-ok.service`). Also renamed: kernel releases (`-beamline-virt`), the preset
(`80-beamline.preset`), refs-file project keys and the tool caches (`~/.cache/beamline/`).
The Lima instance and template stay `myos-builder` until CI moves online, because they hold
the BuildStream cache. `docs/release-model.md` keeps its original wording, with a header note.

Changing the BuildStream project name changes every project-owned cache key, so the first
cycle after the rename rebuilt the kernel and systemd. It also exposed a race in dash's
automake 1.18 sanity check inside the build sandbox. `base/shell-compat.bst` sets
`am_cv_filesystem_timestamp_resolution=1` so the check is deterministic. Verified in
snapshot `20261008.0744`.

## D25. Narrow Virt kernel from allnoconfig

Per spec rev 3 §11.4, `kernel/linux-virt.bst` sets `kernel-base: allnoconfig`. The
configuration step runs `merge_config.sh -n` (allnoconfig with the fragments as
`KCONFIG_ALLCONFIG`), so nothing the fragments do not request is enabled. Profile kernels
with `kernel-base: defconfig` (the future Hardware kernel) keep the defconfig, merge and
`olddefconfig` path. The fragments now spell out what allnoconfig turns off: menus that
default to "y" (`VIRTIO_MENU`, `NETDEVICES`, `BLK_DEV`, `MISC_FILESYSTEMS`, `INPUT`), the
systemd recommendations, and kernel and arm64 hardening (KASLR, strong stack protector,
hardened usercopy, fortify, PAC, BTI, E0PD, KPTI). `CONFIG_MODULES=y` stays for optional
features. The Virt profile itself needs no modules.

Result: an 11 MB Image with no modules (the defconfig kernel shipped a 129 MB modules tree),
and the kernel build drops from about 12.5 to about 2 minutes. The image boots healthy
(`running`, 0 failed units, networkd and resolved working).
