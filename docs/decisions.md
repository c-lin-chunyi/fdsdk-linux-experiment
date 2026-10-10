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

## D26. Extensions are EROFS images on DATA, with a confext for `/etc`

*Spec rev 6 changes the placement during 0.0.3 (§8, D43): per-snapshot, signed verity images
in `/var/lib/beamline/{extensions,confexts}`, linked by the booted snapshot. Until that step
lands, this describes the build.*

Spec rev 5 drops the directory-extension stage (§8, §30). Two facts ruled it out:
- systemd refuses extensions stored under `/usr`. `src/shared/discover-image.c` searches
  `/etc/extensions`, `/run/extensions` and `/var/lib/extensions` only, because overlayfs
  returns `ELOOP` when one lowerdir lies inside another.
- On DATA, a directory tree cannot carry build-time SELinux labels (security §19.1). A large
  desktop tree would need a full relabel on first boot.

An EROFS image built with `mkfs.erofs --file-contexts` is labelled at construction, like
SYSTEM-A. sysext only covers `/usr` and `/opt`, so an extension's `/etc` content ships as a
confext of the same name. Both live on DATA. The default sysext image policy accepts
unprotected images; verity and signatures come with 0.0.3.

## D27. Read-only `/etc`: build-time users, credential-defined dev account

*Spec rev 6 replaces three parts during 0.0.3 (D43): homed accounts instead of the
credential-defined dev account (§18.3), an allowlist of mutable system settings (§14), and a
machine ID saved on DATA. Build-time users and the build-time writers stay. Until those
steps land, this describes the build.*

SYSTEM-A holds the whole root, `/etc` included, as read-only EROFS (spec rev 5 §14). This
breaks anything that writes `/etc` at boot, so:
- **Users.** `systemd-sysusers` runs when the image is built, over the base and every
  official extension's `sysusers.d`. The two are coupled releases.
- **The dev account** is no longer in `sysusers.d`. The test tool passes
  `userdb.transient.user.dev` and `userdb.transient.group.dev` JSON records as credentials,
  which `systemd-userdb-load-credentials.service` loads into `/run/userdb`. The
  non-transient names (`userdb.user.*`) are written to `/etc/userdb` and fail on a
  read-only `/etc`. The password hash
  lives in `tools/qemu-test.py`, never in the image. Without the credential, there is no
  dev account.
- **machine-id.** An empty `/etc/machine-id` gives a transient ID per boot. A
  `system.machine_id` credential can make it stable.
- **Boot-time writers into the root run at build time.** `ldconfig -X -r` builds
  `/etc/ld.so.cache` (`ldconfig.service` runs whenever it is missing), and `systemd-tmpfiles
  --root --boot --create` covers everything outside the state and API filesystems, such as
  `/etc/mtab`. `ConditionNeedsUpdate=/etc` is false on a read-only `/etc`, so the other
  update services skip themselves.

Settings that write `/etc` at runtime (timezone, locale, hostname) fail gracefully. Revisit
with confext-based configuration and with homed.

The journal persists on DATA, but each boot has a new machine ID, so earlier boots appear
as other machines (`journalctl -m` shows them; `journalctl -b -1` does not). A stable ID
derived from the firmware UUID or a credential is a later refinement.

## D28. GNOME from gnome-build-meta recipes, built on Beamline's FDSDK

The owner chose GNOME as the desktop (`desktop-gnome`) and independence over cache reuse.
gnome-build-meta (gbm) master integrates GNOME on FDSDK 26.08 stable plus a patch queue, with
its own systemd recipe (`main`, SELinux disabled). Adopting gbm's FDSDK would have made GNOME
a cache pull, but would also have handed Beamline's FDSDK and systemd selection to gbm.
Instead:
- gbm is junctioned as a recipe library. It is selected as its newest CI-green `master`
  commit, and GNOME component refs come from that commit.
- gbm's `freedesktop-sdk.bst` junction is overridden with Beamline's, so GNOME builds
  against FDSDK master and Beamline's systemd.
- gbm's recipes depend directly on `sdk/glib.bst`, `sdk/gtk.bst`, `sdk/pango.bst` and
  similar. So Beamline's FDSDK junction carries gbm's FDSDK overrides (GLib, GTK 3, Pango
  and others, retargeted into the gbm junction), except `systemd-base`. Changes to that list
  fail the cycle (§31.4).
- gbm's FDSDK patch queue is not applied. At adoption it held three patches (CAS servers,
  zswap, a cups backport), none relevant to Beamline.

Cost: GNOME is built locally. The first build takes hours. Afterwards, every cycle in which
systemd or FDSDK moves rebuilds the systemd-dependent part of GNOME. Revisit if that cost
becomes unbearable; the escape hatches (a visible pin, another selection) are owner
decisions.

**Wiring as built.** `elements/junctions/gnome-build-meta.bst`:
- **Selection and fetch.** It is selected with `gitlab-ci-green` against gitlab.gnome.org
  (a new `gitlab_api` policy field), and fetched by `git_repo` from the describe ref,
  like the FDSDK junction.
- **Overrides.** It overrides gbm's `freedesktop-sdk.bst` with Beamline's. It also
  overrides gbm's two plugin junctions with Beamline's pinned ones: BuildStream refuses a
  plugin project loaded in two contexts, and plugins are Layer 0.
- **recc.** It sets `recc: passthrough`, because gbm's default (`remote-execution`) would
  send compiles to GNOME's servers.

Carrying the list:
- Beamline's FDSDK junction carries gbm's overrides between `BEGIN`/`END gnome-build-meta
  overrides` markers. These are GNOME's SDK libraries, zenity's void element,
  xdg-desktop-portal, flatpak and libical 3.
- Not carried: gbm's systemd family (`systemd-base`, `systemd`, `systemd-ukify`,
  `systemd-libs`) and `linux-module-cert`.
- `integrate.py` compares the list with gbm's at the selected commit and fails the cycle
  on any difference.

The base root is unaffected, since nothing in it depends on the carried libraries.
`bst show` of `core/gnome-shell.bst` resolves 692 elements; 118 gbm elements and about
330 FDSDK elements above the carried libraries build locally.

Measured cost: the first full desktop build took several hours. The first cycle after it,
in which systemd main moved one commit, rebuilt 172 elements in 35.5 minutes on the
12-core builder VM (snapshot `20261008.2309`). That is well below the 1 to 2 hours
estimated above.

## D29. No WebKitGTK or JavaScriptCoreGTK in any artifact

Per spec rev 5 §7.1 and security §8.2. In the GNOME closure, the only path to WebKitGTK
(which also ships JavaScriptCoreGTK) is evolution-data-server's GTK4 OAuth2 sign-in window.
gbm already builds the GTK3 variant off. An override of gbm's
`core-deps/evolution-data-server.bst` adds `-DENABLE_OAUTH2_WEBKITGTK4=OFF` and drops the
`sdk/webkitgtk.bst` dependency. GNOME Online Accounts no longer uses WebKit; it signs in
through the default browser, so Shell's calendar and contacts keep working. libproxy and
polkit use duktape, an interpreter. The one host-side gap is GNOME Shell's captive-portal
window, which loads WebKit at runtime. Virt does not run NetworkManager, so it is decided for
Hardware at 0.1. `tools/check-policy.py` rejects WebKit and JavaScriptCore files in every
artifact tree.

gjs embeds SpiderMonkey, a JIT engine, and gnome-shell cannot run without it. It executes
the shell's own JavaScript from the image, not remote content. Whether the session runs
with the JIT disabled is a Stage 1 question.

## D30. SELinux-aware overrides: systemd, PAM, dbus-broker, erofs-utils

Inspecting the built 0.0.1 image showed that only `libdevmapper` links libselinux. FDSDK's
systemd and linux-pam-base set `-Dselinux=disabled`; dbus-broker leaves SELinux at its
default (off); util-linux has no libselinux in its build sandbox. Stage 0 overrides `components/_private/systemd-base.bst` (already
overridden), `components/linux-pam-base.bst`, `components/dbus-broker.bst` and
`components/erofs-utils.bst`. Two are deferred (security rev 2 §19.2):
- **util-linux.** Overriding `util-linux-libs` would rebuild most FDSDK reverse dependencies.
- **shadow.** It is `--without-selinux` and strips `pam_selinux` from its PAM files, but
  `useradd` never runs against a read-only `/etc`. Beamline ships its own PAM stacks with
  `pam_selinux` instead.

## D31. File modes are restored when filesystems are created

BuildStream artifacts keep only the executable bit. Checking out `image/root-virt.bst` showed
the build-time `/etc/shadow` as 0644. Every file arrives 0644 or 0755, owned by root, and
setuid bits and capabilities are lost. Labels (security §19.1) have the same problem and the
same answer: the element that creates a filesystem applies the metadata. `files/image/permissions`
lists `<mode> <path>` entries. `include/image/permissions.yml` applies them to a writable copy
of the tree in `image/disk-virt.bst` and `image/initrd-virt.bst`, and later in the extension
builder. FDSDK's own VM images do the same: `prepare-image.sh` chmods `/etc/shadow`.

`chmod` in the sandbox cannot set ownership, and is not a good way to record setuid or
capabilities. When the first file needs them, that filesystem is built from a tar stream
carrying explicit metadata (`mkfs.erofs --tar`).

## D32. Linux source: GitHub's archive of the selected master commit

Owner decision, recorded as an explicit trade-off (spec rev 5 §11.2). Measured on
2026-10-08:
- **`git_repo` re-downloads history.** Tracking a branch makes the community `git_repo`
  plugin fetch the new commit with `depth=DEPTH_INFINITE` to compute its git-describe ref
  (`_git_utils.py`). The server answers that "deepen" request with nearly the whole history.
  One Linux bump of 10 commits downloaded a 3.3 GB pack and took 49 minutes: about 35 for
  the download and 14 for dulwich to complete and index it on one thread (849 GB re-read
  from the page cache). The mirror had grown to 11 GB of duplicate packs.
- **git.kernel.org is slow from this host.** It serves about 1.6 MB/s through the
  development host's proxy, even to C git. cdn.kernel.org serves 3 to 10 MB/s, but carries
  only released kernels; release candidates and master commits are not on the CDN.
- **The GitHub archive is fast and stable in practice.**
  `github.com/torvalds/linux/archive/<sha>.tar.gz` is 270 MB, about 45 s here and fast on
  GitHub-hosted runners. Two downloads were byte-identical. Linus's GitHub mirror matched
  git.kernel.org master.

So `tools/integrate.py` resolves the commit with `git ls-remote` against git.kernel.org,
which stays the authority for the commit ID. It warns if GitHub's mirror differs, writes
the commit to `include/kernel/linux-commit.yml`, and lets `bst source track` pin the
archive's sha256 in `project.refs`. The nearest tag comes from the commit's `Makefile` and
GitHub's compare API, best effort.

The trade-off: GitHub's archive bytes are stable by practice, not by guarantee. GitHub
changed them once, in 2023, and reverted. A changed archive would only affect refetching
an old snapshot's source, which promotion never does. The commit in the manifest lets the
source be rebuilt from git if needed.

A release tarball from cdn.kernel.org (`latest_stable`) was the alternative. It is
signed and immutable, but would have kept the kernel about one release cycle behind HEAD.

## D33. Tracked git sources use the classic `git` source

The `git_repo` behaviour described in D32 also hit systemd: each move of systemd `main`
re-downloaded its whole history (410 MB, then 550 MB) and spent about 45 s processing it.
systemd's recipe runs `git describe` at build time (`-Dversion-tag`), so it needs a real
`.git` directory, not an archive. The classic `git` source from the pinned
`buildstream-plugins` junction fits:
- it fetches with C git (`git fetch --prune <url> +refs/heads/*:refs/heads/* +refs/tags/*:refs/tags/*`);
- it negotiates against the whole mirror, so a cycle downloads only new objects;
- `ref-format: git-describe` gives the same ref format as before.

`overrides/systemd-base.bst` and `base/shell-compat.bst` use it, as will every
project-owned source tracked at a branch. FDSDK's own elements keep `git_repo`. They are
built from fixed describe refs, which `git_repo` fetches shallowly and cheaply.

## D34. SYSTEM-A and DATA layout details

The 0.0.2 layout (spec rev 5 §14, §15) as built by `files/repart/virt`:
- **SYSTEM-A** is `Type=root`, EROFS with `lz4hc`, in a fixed 1 GiB partition. The
  filesystem itself is minimal (about 107 MB). The fixed size leaves room for SYSTEM-B and
  sysupdate at 0.0.3. The kernel takes `root=PARTLABEL=SYSTEM-A rootfstype=erofs ro`
  until verity discovery replaces it.
- **DATA** is `Type=linux-generic`, label `data`, shipped as a 512 MiB ext4 holding `var/`
  and `home/`. At first boot, the `/usr/lib/repart.d` definitions from the Virt profile
  let `systemd-repart` grow the partition to the end of the disk (ESP and SYSTEM-A are
  capped at their sizes). Then `x-systemd.growfs` grows the filesystem when `/etc/fstab`
  mounts `/data`, ordered after repart. On an 8 GB disk it reaches 6.6 GB.
- **Repart validation.** Both partitions set `AddValidateFS=no`: the build sandbox cannot
  store the `user.validatefs.*` xattrs, and neither partition is mounted through gpt-auto.
- **The initrd** drops `/etc/fstab` and `/usr/lib/repart.d` from its copy of the root. DATA
  belongs to the host after switch-root. In the initrd, repart cannot find `/sysroot` yet
  and failed the boot.

## D35. SELinux Stage 0 policy structure

The policy (security rev 2 §7, §16) has three parts.

**Kernel-defined part, generated.** Object classes, their permissions, the 27 positional
initial SIDs and the policy version belong to the kernel. `kernel/selinux-headers.bst`
installs `classmap.h`, `initial_sid_to_string.h` and `security.h` from the same Linux
source as the kernels; it is resolved with the kernel by `integrate.py`. At build time,
`files/selinux/kernel-cil.py` turns them into `kernel.cil`: 97 classes, `sidorder`, MCS
`s0` with `c0.c1023`, and policy version 35 for Linux 7.3. A new kernel class therefore
appears in the policy without anyone editing it.

**Project-written part, in CIL.** `files/selinux/policy/`:
- users `system_u`/`user_u` and roles `system_r`/`user_r` (plus `object_r`, which CIL
  requires to be declared);
- the integrity attributes `beamline_platform_domain` (P3) and `beamline_user_domain` (P0);
- `kernel_t`, `init_t` (entered through `init_exec_t` on `/usr/lib/systemd/systemd`) and
  `user_t`;
- file types for SYSTEM, DATA and the kernel filesystems;
- `fsuse` and `genfscon` labelling, and file contexts.

**Stage 0 rules.**
- Platform domains get every permission of every class except `security`. There they get
  no `setenforce`, `load_policy`, `setbool`, `setsecparam` or `setcheckreqprot`, and a
  `neverallow` on `setenforce`/`load_policy` holds for every domain.
- Object types may associate with any filesystem.
- User domains get no rules. Their denials, recorded in each manifest, are what Stage 1
  designs.
- `handleunknown allow` remains until Stage 1.

**Tools.** `security/selinux-tools.bst` builds `secilc` and `setfiles` from SELinux
userspace `main` (`libsepol.a` and `libselinux.a` linked in) under
`/usr/libexec/beamline/selinux-tools`. It is a build dependency only. The policy element
compiles the policy, then validates the file contexts with `setfiles -c`.

**Runtime pieces.**
- With SELinux, dbus-broker refuses to start without
  `/etc/selinux/<type>/contexts/dbus_contexts`, so the policy ships a minimal one.
- Console login uses a project-owned `/etc/pam.d/login` with `pam_selinux` (D30).
  systemd's own `systemd-user` stack gains `pam_selinux` once systemd is built with
  SELinux.
- `beamline-selinux-ok.service` (`ConditionSecurity=selinux`) prints
  `BEAMLINE_SELINUX_OK`, which `ci/boot` requires before `BEAMLINE_BOOT_OK`.
- The policy also declares the classes userspace object managers ask about:
  dbus-broker's `dbus` (`acquire_svc`, `send_msg`), systemd's `service`, and systemd's
  permissions on the kernel's `system` class. Undeclared, libselinux answered
  "Unknown class" in the desktop session.
- `beamline-avc-report.service` prints the boot's audit AVC records on the console.
  `integrate.py record` collects the kernel's and the journal's copies into
  `manifest.selinux` (`policy_loaded`, `mode`, distinct denials).

Verified on the first labelled image:
- PID 1 runs as `system_u:system_r:init_t:s0-s0:c0.c1023`;
- the dev login shell runs as `user_u:user_r:user_t:s0`;
- `/sys/fs/selinux/enforce` is 0;
- the boot test records no denials, and a login session records the expected `user_t`
  ones.

## D36. Extension pipeline, admin on demand, uutils through `cargo`

**Composition.** An extension is built in two elements:
- `extensions/<name>-tree.bst` composes the Virt base, the integration toolbox and the
  extension content together, so FDSDK's integration commands see the merged tree.
- `extensions/<name>.bst` (`include/extension.yml`) runs `tools/build-extension.py`. Every
  path the finished root lacks becomes content: `/usr` and `/opt` go to the sysext, `/etc`
  to the confext. The root's policy removals (`su`) are dropped. So are integration
  toolbox files, but only when they are the toolbox's own. A path the extension's own
  content stack also has stays (the toolbox closure shares libraries with extensions), and
  so does uutils' `ls` link at the path where the toolbox has GNU's `ls`. A path the root has with different content
  fails the build, because an extension adds to the base and never replaces it.
- An extension's composition includes only the parts of the toolbox it needs. FDSDK's
  integration commands run on uutils in the admin tree, so only `gzip` is added there;
  GNU coreutils would collide with uutils.
- The narrow Virt kernel needed `CONFIG_BLK_DEV_LOOP`: raw extension images are attached
  through loop devices.

The builder writes `extension-release.<name>` (`ID`, `SYSEXT_LEVEL`/`CONFEXT_LEVEL`,
`ARCHITECTURE`, scope `system`). It applies the permission list,
`check-policy.py --artifact` vets every tree, and `mkfs.erofs -zlz4hc --all-root` builds
the images with the base policy's `--file-contexts`.

**Artifact rules.** `check-policy.py --artifact` applies to the root and every extension:
- no `su`, `sudo`, package managers or `dracut`;
- no binary carrying the "GNU coreutils" signature (shipped coreutils are uutils);
- no WebKit or JavaScriptCore files (D29).

Matching the signature instead of utility names leaves procps's `kill` and `uptime` alone.

**Admin is on demand.** `admin.sysext.raw` is placed on DATA at
`/var/lib/beamline/extensions/`, outside the sysext search path. `beamline-admin.service`
links it into `/run/extensions` with `systemd-tmpfiles --inline` and runs
`systemd-sysext refresh` (stop reverses both); there is no shell. Nothing enables it.
`ci/test-extensions` injects a check unit through a `systemd.extra-unit` credential, pulls
it in with `systemd.wants=` (SMBIOS `io.systemd.stub.kernel-cmdline-extra`), and expects
`BEAMLINE_ADMIN_OK` from `bash --version` and uutils `ls --version`.

**uutils.** `admin/uutils-coreutils.bst` builds the multicall `coreutils` with
`--features unix` and links one symlink per utility, except `kill` and `uptime` (procps)
and `more` (util-linux). Crates come from the `cargo` source of the pinned
`buildstream-plugins` junction, not `cargo2`. Under `ref-storage: project.refs`,
BuildStream resets every source's ref with `set_ref(None)`. `cargo2` reports a missing ref
as an empty list and then crashes on `None` (`cargo2.py`), so it cannot load without a
ref. FDSDK's and gnome-build-meta's `cargo2` elements are unaffected, because their
projects keep refs inline.

**Layer 0 addition.** `cargo2`, which the community plugin junction ships and FDSDK's
and gnome-build-meta's Rust elements use, imports `tomlkit`. `ci/bootstrap` now installs
`python3-tomlkit` (Fedora 44) next to `python3-dulwich`; the builder VM got the same
package. This was a deliberate change outside any integration cycle (§31.3).

## D37. bash without /usr/bin/sh, through a project-owned filter

Owner decision. FDSDK's bash installs `/usr/bin/sh -> bash`. In any tree that holds both
bash and the base (the admin extension's composition), that link collides with dash's
`/usr/bin/sh`. Rather than let dash win through an `overlap-whitelist`, bash's link is
dropped before it reaches any tree. `/usr/bin/sh` is dash everywhere (§6).

A BuildStream `filter` selects split domains from its parent's public data. FDSDK
defines none that isolates `/usr/bin/sh`; its `shells` domain covers only fish and zsh
data. So the filter is three small elements:
- `admin/bash-artifact.bst` is a `kind: filter` over `bootstrap/bash.bst` that keeps bash's
  own runtime files (orphans included; no debug, devel or doc) and none of its dependencies;
- `admin/bash-without-sh.bst` (a script element) copies that artifact without
  `/usr/bin/sh`;
- `admin/bash.bst` is a stack of it and bash's runtime dependency, `bootstrap/readline.bst`.
  Script elements cannot declare runtime dependencies themselves.

The admin stack uses `admin/bash.bst`. `base/shell-compat.bst` no longer carries an
overlap whitelist for `/usr/bin/sh`.

## D38. desktop-gnome composition and configuration

*Spec rev 6 ends GDM autologin during 0.0.3 (§18.3, D43): homed needs the password, so the
greeter signs the user in, and polkit moves to the base. The rest stands.*

Taken without asking, per the owner's instruction for 0.0.2. Revisitable.

**Content.** `desktop/gnome.bst` takes from gnome-build-meta:
- GDM, GNOME Shell, Mutter, Session, Settings Daemon and Settings;
- Nautilus, Software, GVfs and the backgrounds;
- accountsservice, upower, dconf, power-profiles-daemon and oo7 (secret service, PAM
  module, portal);
- the GNOME and GTK portal backends and xdg-user-dirs-gtk;
- Adwaita icons and fonts, Cantarell, the settings schemas and glib-networking.

From FDSDK it takes PipeWire with WirePlumber, xdg-desktop-portal and flatpak (both at
gbm's selection, D28), polkit, Mesa in FDSDK's VM layout (`vm/mesa-default.bst`), the
Flathub remote and FDSDK's user preset for the PipeWire sockets. File Roller is
project-owned (`desktop/file-roller.bst`, `master`, without PackageKit, with Nautilus'
actions).

gjs and mozjs link `libreadline` without declaring it. On FDSDK 26.08, gbm's base, it is
provided anyway; on FDSDK master nothing pulls it in, and GNOME Shell failed with
`libreadline.so.8: cannot open shared object file`. The desktop stack declares
`bootstrap/readline.bst` itself. Report it to gnome-build-meta.

Left out: gnome-console and every other utility (Flatpak); orca, rygel, remote desktop,
user share, tour and yelp; gnome-initial-setup, which cannot create users with a read-only
`/etc`. gnome-software keeps gbm's options (Flatpak, fwupd, snap, sysupdate backends)
rather than adding an override to trim them.

**Session.**
- GDM is built by gbm with `selinux=disabled`. gbm's element ships its own PAM stacks
  (`pam_gdm`, oo7 keyring unlock, `postlogin`) but without `pam_selinux`.
  `files/desktop/gnome` replaces `gdm-autologin` and `gdm-password` with copies that add
  the `pam_selinux` close/open pair around `pam_loginuid` (an overlap whitelist, staged
  after gdm). These copies are not drift-checked: compare them with gbm's when GDM's
  stacks change. The greeter's `gdm-launch-environment` stays gbm's.
- `/etc/gdm/custom.conf` logs `dev` in automatically. That account exists only when the
  boot credential defines it (D27).
- The confext carries the `display-manager.service` alias. A desktop preset keeps
  NetworkManager and ModemManager disabled, since Virt stays on systemd-networkd; they ship
  only because Shell and Settings link their libraries.
- The Virt kernel gains DRM with virtio-gpu KMS, evdev, virtio-sound and fanotify, but no
  VTs or framebuffer console. GDM and Mutter run on a logind seat without VTs.

**Extension build.**
- `extensions/desktop-gnome-tree.bst` composes base and desktop with FDSDK's integration
  commands (schemas, loaders, linker cache).
- `extensions/desktop-gnome.bst` applies system and user presets to a copy of the merged
  tree (`extension-presets`), so enablement ships in the confext.
- `/etc/ld.so.cache` is the one file allowed to differ from the base (`--regenerated`).
  Built from the merged tree, it lets the dynamic loader find Mesa's `GL/default`
  libraries, and it shadows the base's cache only while the confext is merged. For that,
  the base carries FDSDK's `integration/ldconfig.bst`: its `/etc/ld.so.conf` includes
  `ld.so.conf.d/*.conf`, and the desktop adds Mesa's path as a snippet.
- Both images go to DATA's search paths, `/var/lib/extensions` and `/var/lib/confexts`,
  and merge at boot. DATA ships at 3 GiB, enough for the images (about 1 GB). An offline
  `Minimize=guess` made it a 1.5 TB sparse ext4 and spent 88 minutes copying it.

**System users.** Required fixed identities belong to the base release definition (spec
§18.2), and `/etc` is read-only. So `extensions/desktop-gnome-sysusers.bst` collects the
desktop's new `sysusers.d` files, and `image/root-virt.bst` borrows them while running
`systemd-sysusers`: gdm, polkitd, colord and the rest end up in SYSTEM's `/etc/passwd`. The
files themselves ship with the extension. As a consequence, the base root is built after
the desktop composition; they are coupled releases.

## D39. Desktop test through injected units and a QMP screenshot

`ci/test-desktop` boots the image with a 2D virtio-gpu (software rendering) and 4 GB of
memory. The check is injected like the admin check (D36), so nothing test-only enters an
image:
- a path unit fires when `/run/user/1000/bus` appears, meaning GDM's automatic login has
  started the session;
- the check service, running as `dev`, waits up to 480 s for `org.gnome.Shell` on the
  session bus (`gdbus wait`);
- it requires `pipewire` and `wireplumber` to be active, pings the portal (which is
  D-Bus activated, so asking systemd whether it is active was wrong), runs
  `flatpak --version`, and starts an unprivileged bubblewrap sandbox;
- it then prints `BEAMLINE_DESKTOP_OK`.

After the marker, `tools/qemu-test.py` takes a QMP `screendump` and fails on a uniform
image. This replaces the plan's virtio-serial marker port, which would have needed a udev
rule in the image.

`ci/boot` and `ci/test-extensions` now mask `systemd-sysext.service` and
`systemd-confext.service` through the kernel command line. The base boot therefore checks
§5.1: the base boots healthy without any desktop. The merged system is the desktop test's
subject. `--gpu gl` with `--qemu` (or `QEMU_SYSTEM`) gives an interactive accelerated
session on a QEMU built with virglrenderer, such as the owner's UTM build. Automated tests
stay headless 2D. Each manifest gathers AVC denials from all three VM tests and keeps the
screenshot.

## D40. The builder VM keeps time from the host only

The first desktop build failed in gnome-build-meta's glib (meson: "Clock skew detected …
0.2247s in the future") and rpcsvc-proto (automake: "newly created file is older than
distributed files"). The builder clock was jumping backwards:
- chronyd's only NTP source was reached through the development host's proxy (a fake-IP
  address, ±119 ms jitter). It had set the kernel tick to 10743 instead of 10000, so the
  guest clock ran 7.4% fast.
- Lima's guest agent pulled the clock back to the host's about every 10 s, by about 744 ms
  each time.

Files written just before a step carried future timestamps. dash's earlier automake failure
(D24) was most likely the same thing.

Lima's host synchronisation is the right time source for the VM. chronyd is disabled
(`lima/myos-builder.yaml` provisions it so), and the existing builder had chronyd stopped
and its tick and frequency reset through `adjtimex`. This is a deliberate Layer 0 change
outside any integration cycle (§31.3). Hosted Linux runners keep their own NTP.

## D41. Re-queue the default target after extensions merge

The first desktop boot merged desktop-gnome but never started GDM. `graphical.target`
lists `display-manager.service`, but PID 1 computes the boot transaction before
`systemd-sysext.service` and `systemd-confext.service` merge the images from DATA. At that
point the alias and `gdm.service` do not exist yet, so they get no job; the merge's daemon
reload makes them known but queues nothing. `beamline-extensions-start.service` runs after
both merges and calls `systemctl start --no-block default.target`. The default target's
wants are evaluated again, and units the extensions brought start in the same boot.
Without extensions it is a no-op.

This needed one more piece: `systemd-sysext` and `systemd-confext` reload the service
manager after merging only when an extension's release file says
`EXTENSION_RELOAD_MANAGER=1` (`src/sysext/sysext.c`). Without it, `gdm.service` was on disk
but PID 1 still reported it `not-found`. `tools/build-extension.py` sets the field on every
image that carries unit files. Merging in the initrd is not an option: the images live
on DATA, which the host mounts.

## D42. Desktop bring-up findings

The desktop test surfaced three gaps, each fixed where it belongs:
- **Namespaces.** The allnoconfig Virt kernel had user namespaces but not the UTS, IPC, PID,
  network or time namespaces, so bubblewrap (Flatpak) could not create its sandbox.
  `common.config` now requests all of them. systemd's service sandboxing needs them as well.
- **Undeclared runtime dependency.** GNOME Shell needs `libreadline`, which gjs and mozjs
  link without declaring (D38).
- **Units from extensions.** They need `EXTENSION_RELOAD_MANAGER=1` and a re-queued default
  target (D41).

## D43. 0.0.3 direction: homed, run0, scoped `/etc`, then Stage 1

Decided with the owner on 2026-10-09, after 0.0.2. D26 to D42 were reviewed; only the parts
noted in D26, D27 and D38 change. 0.0.3 takes §38's list plus three of the owner's directions,
written into spec rev 6:
- **Human accounts are systemd-homed users**, on LUKS2 home images with btrfs inside (§18.3).
  This also removes any need for a writable shadow. homed authenticates on every activation,
  for every storage type (`src/home/homework.c`, `home_activate()` calls
  `user_record_authenticate()`), so GDM autologin ends; the desktop test signs in through
  the greeter. Accounts come from `home.create.<user>` credentials, which `homectl
  firstboot` reads.
- **Root is locked with a nologin shell; run0 is the only escalation** (§18.1, §19). polkit
  sees run0 only as `StartTransientUnit(<unit>, "start")` under
  `org.freedesktop.systemd1.manage-units` (`src/core/dbus-manager.c`), never the command.
  So polkit decides who (wheel, with the user's own password; everyone else is refused), and
  a confined SELinux admin domain decides what.
- **Scoped mutable `/etc`** (§14). `systemd-confext`'s mutable mode supplies the writable
  layer; it works with no extension merged ("No extensions found, proceeding in mutable
  mode", `src/sysext/sysext.c`). SELinux file types scope it to the system settings that
  hostnamed, timedated and localed write. The machine ID cannot live there, because PID 1
  reads `/etc/machine-id` before any confext merges. It is saved on DATA and bound in by the
  initrd instead.
- **Update signatures use gpg.** systemd-pull verifies only `SHA256SUMS.gpg`, by running
  `gpg` (`src/import/pull-common.c`), so the `gpg` binary joins the base, alone.

Order, one structural change per green cycle: machine ID, development keys and signed UKIs,
verity, the A/B layout with XBOOTLDR and the RecoveryOS stub, signed extensions, sysupdate,
homed, root and run0, scoped `/etc`, then SELinux Stage 1 (policy completion while
permissive, then enforcement). Stage 1 comes last so the enforcing policy covers everything
before it. Each step's details get their own entry when it lands.

## D44. Channels: `latest` and `edge`; no `stable`

The owner renamed `latest-green` to `latest` and dropped `stable` (spec rev 6, §17.3).
Confidence is expressed by `edge` and by checkpoints, not by a slower lane.
`tools/integrate.py` keeps the pointer in `out/snapshots/latest.json`; the existing
`latest-green.json` was renamed once. `docs/release-model.md` keeps its original names, with
a note. Earlier entries keep the names they were written with.

## D45. The machine ID is saved on DATA and bound in by the initrd

*Superseded by D56: the initrd merges /etc's mutable layer, which holds /etc/machine-id, and the
stock systemd-machine-id-commit saves the ID. The project's initrd machine-ID units are gone;
"uninitialized" still marks a first boot.*

0.0.3 step 1 (spec rev 6 §14). PID 1 reads `/etc/machine-id` at startup, before any unit
runs (`src/core/main.c`), so the ID cannot come from the mutable `/etc` layer or from
anything the host mounts. The initrd provides it:
- SYSTEM ships `/etc/machine-id` as `uninitialized`. That marks a first boot: PID 1
  overmounts a transient ID, and a host tmpfiles `C` line saves it as
  `/var/lib/beamline/machine-id` on DATA. The previous empty file was never a first boot,
  which would also have kept `systemd-homed-firstboot` from running.
- On later boots, `beamline-machine-id.service` in the initrd mounts DATA read-only
  (`run-beamline-data.mount`, unmounted again when the service ends), copies the saved ID to
  `/run/beamline/machine-id`, and `sysroot-etc-machine\x2did.mount` binds it read-only over
  `/sysroot/etc/machine-id`. PID 1 finds a valid ID, the boot is not a first boot, and
  `journalctl -b -1` works.
- DATA itself stays a host mount: mounting it read-write in the initrd would move its
  first-boot growth (systemd-repart, then growfs) out of order. Copying to `/run` keeps the
  read-only initrd mount from pinning DATA's superblock read-only.
- The units carry `ConditionPathExists=/etc/initrd-release`, so they are inert in the host.
  `image/initrd-virt.bst` adds the bind mount to `initrd-fs.target.wants`.

A new DATA, or a disk image booted for the first time, gets a new ID. `ci/test-reboot`
boots twice and checks the previous boot is in this machine's journal.

## D46. Development keys, signed UKIs and enforced module signing

0.0.3 step 2 (spec rev 6 §38, security §5.4, §19.4).
- **Keys.** `tools/make-dev-keys` generated them once, in the builder (openssl, gpg), into
  `files/keys/dev`, one per scope. Each certificate's subject says "DEVELOPMENT ONLY, NOT
  TRUSTED". They are committed on purpose, so every build signs the same way and stays
  reproducible.

  | Scope | Key | Signs |
  |---|---|---|
  | `uki/` | Secure Boot db (RSA 2048) | UKIs and systemd-boot |
  | `verity/` | RSA 2048 | extension root hashes (step 5) |
  | `update/` | OpenPGP ed25519; armored secret key plus the binary keyring systemd-pull reads | SHA256SUMS (step 6) |
  | `kernel-modules/` | RSA 4096, key and certificate in one PEM, as kbuild expects | kernel modules |
- **Build access by scope.** Each signing element stages only its own scope.
  `security/keys-uki.bst` serves `image/uki-virt.bst`. The Virt kernel takes its key as a
  local source into `certs/`.
- **UKI and boot loader.**
  - ukify signs with `systemd-sbsign`, from Beamline's systemd `main`. It also signs the
    embedded kernel (`--sign-kernel`); without that flag, ukify calls the signing tool's
    verify, which `systemd-sbsign` lacks.
  - systemd-boot is signed with `systemd-sbsign` as well.
  - FDSDK's `sbverify` (sbsigntools) checks both against the development certificate. A
    missing or wrong signature fails the element.
- **Secure Boot is not enforced.** QEMU tests do not enrol keys or enable Secure Boot (out of
  scope; security §19.5). Until production keys exist, the production UKI is
  development-signed too (security §19.4).
- **Modules.** The kernel sets `MODULE_SIG`, `MODULE_SIG_FORCE`, `MODULE_SIG_ALL`, SHA-256 and
  `MODULE_SIG_KEY="certs/module-signing.pem"`. The name is not kbuild's default
  `certs/signing_key.pem`, so kbuild never generates a key in its place. The Virt kernel ships
  no modules, so the effect is that nothing unsigned can ever load. Step 11 tests it.

## D47. SYSTEM under dm-verity: root hash in the signed UKI, built in three stages

0.0.3 step 3 (spec rev 6 §13, §14).
- **Discovery by root hash.** The signed command line carries `roothash=` and no `root=`.
  With `roothash=` set, systemd's gpt-auto generator stands down. The veritysetup generator
  derives the data and hash partitions' UUIDs from the hash (first and last 128 bits,
  `src/veritysetup/veritysetup-generator.c`) and sets up `/dev/mapper/root`, which
  fstab-generator mounts. A UKI therefore boots exactly the SYSTEM image it was built with,
  which is what A/B slots need.
- **Three stages, as mkosi does it:**
  1. `image/system-virt.bst` runs `systemd-repart --split=yes --json` over the root (EROFS,
     labelled, `Verity=data`) and its hash tree (`Verity=hash`). Both are minimised. It keeps
     the split images and the JSON.
  2. `image/uki-virt.bst` reads the root hash from that JSON.
  3. `image/disk-virt.bst` places the split images with `CopyBlocks=` in fixed-size
     partitions (SYSTEM-A 1 GiB, SYSTEM-A-VERITY 64 MiB).

  With `CopyBlocks=`, repart neither computes verity nor derives UUIDs, so the disk element
  adds a definition drop-in with each partition's UUID from the JSON. File modes are
  restored and labels applied in stage 1, where the tree is packed.
- **Device-mapper's udev rules.** The first verity boot hung in the initrd:
  systemd-veritysetup activates through libdevmapper, which waits for udev to confirm each
  device (`95-dm-notify.rules` runs `dmsetup udevcomplete`), and `10-dm.rules` is what names
  `/dev/mapper/root`. FDSDK ships them only in its full lvm2. `base/device-mapper-files.bst`
  copies `dmsetup` and three rules out of it (D37's script pattern), and
  `base/device-mapper.bst` adds libdevmapper. Trees that also carry all of lvm2
  (desktop-gnome, through udisks) get identical copies, whitelisted as overlaps.
- **The tamper test** (`ci/test-verity`) writes a pattern over SYSTEM-A's first block in the
  throwaway overlay (`qemu-io`), never in the image, and expects the kernel's verity
  corruption report. This is security §15's "modifies verified /usr: integrity failure".

## D48. The 0.0.3 disk layout, three UKIs and the RecoveryOS stub

0.0.3 step 4 (spec rev 6 §13, §15, §16, §20).
- **Layout**, in GPT order:

  | Partition | Size | Content |
  |---|---|---|
  | ESP | 256M | systemd-boot and `loader.conf` only |
  | XBOOTLDR | 1G, vfat | the UKIs in `/EFI/Linux`, where systemd-boot finds them |
  | SYSTEM-A, SYSTEM-A-VERITY | 1G, 64M | |
  | SYSTEM-B, SYSTEM-B-VERITY | 1G, 64M | |
  | RECOVERY, RECOVERY-VERITY | 1G, 64M | |
  | DATA | grows | |

  The image ships the whole layout, so tests exercise it as installed. The raw image is
  sparse.
- **Slot labels follow systemd-sysupdate.** An installed slot (data and hash partition alike)
  is labelled `beamline_<snapshot>`, a free one `_empty`. "SYSTEM-A/B" are roles in the spec,
  not labels; nothing mounts SYSTEM by label any more (D47).
- **RECOVERY has Beamline's own partition types** (`a4708229-…` and `87d71729-…`), so neither
  sysupdate (which matches `root` partitions) nor the boot-time repart definitions (which
  match `linux-generic` for DATA) can ever take them. They are empty until the RecoveryOS
  becomes real.
- **Three UKIs**, same kernel and initrd, all signed with the development key:
  - `beamline_<snapshot>.efi`, production;
  - `beamline-dev_<snapshot>.efi`, the same plus `enforcing=0` (security §19.4). It is a
    separate file, because the two will carry different signatures once production keys
    exist. A multi-profile UKI would put both command lines under one signature.
  - `beamline-recovery.efi`, the stub: `rd.systemd.unit=beamline-recovery-stub.target`,
    which prints `BEAMLINE_RECOVERY_STUB` and powers off. No root is mounted:
    `rd.systemd.gpt_auto=0`, because without `roothash=` the gpt-auto generator tries to
    activate a SYSTEM slot's verity device and fails.

  Each UKI's os-release names it (`IMAGE_ID`, a PRETTY_NAME suffix), so the boot menu tells
  them apart. `loader.conf` defaults to `beamline_*`: the newest production UKI.
- **Boot counting**: `systemd-boot-check-no-failures` is preset-enabled, so
  `boot-complete.target` means "no unit failed"; `systemd-bless-boot` comes from its
  generator. The shipped UKIs carry no counter; sysupdate adds one to the UKIs it installs
  (step 6).
- `/efi` and `/boot` exist in SYSTEM as mount points for the ESP and XBOOTLDR.
- **The test** (`ci/test-boot-entries`) chains three boots in one QEMU run with `bootctl
  set-oneshot`: production by default, then development (`enforcing=0`), then the stub.

## D49. Develop frozen, then integrate HEAD as its own step

Decided by the owner on 2026-10-09, during 0.0.3 step 4. Every integration cycle moved all
tracked HEADs, so each structural step paid for whatever had moved upstream: systemd moved
three times in one afternoon, and each move rebuilds about 170 elements, GNOME included, in
around 35 minutes. A failure would also mix a structural change with an upstream regression,
against §35's one dimension at a time.

The model now:
- **Package steps are frozen.** `./ci/integrate --frozen` keeps every tracked component at
  the commits the snapshot `latest` recorded. It asks upstream nothing and checks that the
  working tree's refs are exactly those. The build reuses the cache, and only the project's
  own change is tested. A green frozen cycle is recorded as a snapshot like any other, with
  `mode: frozen`, `frozen_from` and HEAD conformity "frozen at <snapshot>" in its manifest.
  That gives later steps predecessors, such as step 6's upgrade test.
- **HEAD integration is a step of its own.** When a package is complete, a plain
  `./ci/integrate` resolves every HEAD, with no structural change in it. If it fails, the
  cause is upstream, not the package.

This is an explicit, visible freeze of the whole source set, not a pin for a broken
component: nothing is substituted silently (§17.2), and the manifest says what was frozen
and from which snapshot. `record --result aborted` closes an interrupted cycle without
claiming the inputs failed. The step 4 cycle that was interrupted for this decision is
recorded as aborted (integration 20261009.1027).

## D50. Signed, verity-protected extensions, one set per snapshot

0.0.3 step 5 (spec rev 6 §8, security §6.2, §15). Supersedes D26's placement.
- **Format.**
  - Every sysext and confext is a disk image built by `systemd-repart --offline`, with three
    partitions: EROFS in a root partition, labelled from the base policy's file contexts; a
    dm-verity hash tree; and a signature over the root hash, made with the development verity
    key (`files/repart/extension`, `security/keys-verity.bst`).
  - A root partition keeps the paths inside equal to the paths after merging, so one
    `file_contexts` labels SYSTEM and every extension (security §19.1).
  - `build-extension.py` still splits the trees. Each image is seeded from its own UUID file,
    so it is reproducible.
- **Trust.**
  - `base/verity-trust.bst` installs the certificate alone as
    `/usr/lib/verity.d/beamline-development.crt`. That is one of systemd's `verity.d` search
    paths, so the trust is part of SYSTEM.
  - The kernel checks the signature since D53. Before that, systemd checked it in userspace:
    the kernel refused the signed table ("Unrecognized verity feature request:
    root_hash_sig_key_desc"), and systemd fell back.
  - Drop-ins for `systemd-sysext.service` and `systemd-confext.service`, and
    `beamline-admin.service`, pass `--image-policy=root=signed+absent:usr=signed+absent`.
    That is systemd's own strict sysext policy (`image_policy_sysext_strict`), applied to
    every extension.
- **Coupling.**
  - `SYSEXT_LEVEL` and `CONFEXT_LEVEL` are the snapshot identifier, in os-release and in every
    extension-release (spec §8's "base-42 / desktop-gnome-42"). An image therefore merges only
    into the SYSTEM built with it; systemd skips the others.
- **Placement.**
  - DATA keeps every snapshot's images under their own names:
    `/var/lib/beamline/{extensions,confexts}/<name>_<snapshot>.raw`.
  - At boot, `beamline-extensions-link.service` links desktop-gnome's pair for this SYSTEM
    (`%A`, its `IMAGE_VERSION`) into `/run/extensions` and `/run/confexts`, before the merges.
  - `beamline-admin.service` links admin's pair the same way, on demand.
  - The image name systemd sees is the link's name, which matches the extension-release file.
    After a rollback the older SYSTEM links its own images. sysupdate keeps two sets (step 6).
  - `/var/lib/extensions` and `/var/lib/confexts` stay empty.
- **Test.**
  - `ci/test-extensions` adds a boot with three copies of the admin image, tampered on the host
    (`qemu-test.py --attach-tampered`):
    - one character of the signature changed;
    - the first EROFS block overwritten;
    - the signature partition retyped as generic data, so the image is unsigned.
  - Each copy is offered as `admin.raw` in turn, and none may merge. Then the signed image
    merges through `beamline-admin.service`.

## D51. Extensions depend only on the base image

Decided by the owner on 2026-10-09, withdrawing an earlier idea of one extension layered on
another (spec rev 6 §8). Every extension depends only on the base image of its snapshot.
There is no dependency graph between extensions and no layering. A variant of an extension,
such as a future `desktop-gnome-advanced` with GNOME Shell extension support beside a
`desktop-gnome` without it, is a separate, complete extension. The two are mutually exclusive
alternatives.

The build already works this way: `tools/build-extension.py` makes each extension from its
composed tree minus the base, and fails on conflicts with the base. Alternatives naturally
overlap (both carry GNOME Shell), so when they exist, the boot-time link step
(`beamline-extensions-link.service`, D50) links at most one of each set.

## D52. systemd-sysupdate following a signed channel directory

0.0.3 step 6 (spec rev 6 §16, security §14.1, §15).
- **A snapshot's update artifacts** come from `image/update-virt.bst`:
  - the production and development UKIs;
  - SYSTEM and its verity hash tree, named `beamline_<snapshot>_<uuid>.root{,-verity}.raw`, with
    the UUIDs derived from the root hash;
  - the four extension images, as `<name>_<snapshot>.{sysext,confext}.raw`;
  - `SHA256SUMS` and `SHA256SUMS.gpg`.

  The manifest is signed with the development update key. Ed25519 is deterministic and gpg's
  clock is frozen at the key's creation time (it refuses to sign before it), so the artifact
  is reproducible.
- **Transfers** (`/usr/lib/sysupdate.d`):
  - the production UKI goes to XBOOTLDR with three boot attempts and two instances;
  - the development UKI goes to XBOOTLDR;
  - SYSTEM and its verity tree go into the free root and root-verity slots;
  - the extensions go to `/var/lib/beamline/{extensions,confexts}`, two instances each, so a
    rollback finds its own (D50).

  Every transfer sets `Verify=yes` and protects the booted version. The URL is a placeholder
  until publication (0.1), and tests replace the files through `/run/sysupdate.d`.
- **Verification uses gpg**, decided with the owner. systemd-pull verifies only
  `SHA256SUMS.gpg`, by running `gpg` (`src/import/pull-common.c`).
  - The base gets the `gpg` binary alone (`base/gpg-files.bst`, D37's pattern) and the three
    libraries the base lacked: libassuan, npth and readline.
  - systemd-pull trusts its vendor keyring, plus `/etc/systemd/import-pubring.pgp` when present.
    `image/root-virt.bst` replaces the vendor keyring systemd ships (other distributions' keys)
    with Beamline's, so only Beamline's key is trusted. The extension build excludes that
    path, like su (`tools/build-extension.py` now applies exclusions before its base-conflict
    check).
- **The channel is a directory.** `tools/integrate.py record` copies the update artifacts into
  `out/snapshots/<id>/update/` and points `out/channels/latest` at it; promotion only relinks.
  Only the two newest snapshots keep their update artifacts (about 1.2 GB each).
  - The signature covers a snapshot's manifest, not a channel or a moment, so a replayed older
    manifest (a freeze attack) is not detected yet. sysupdate understands `BEST-BEFORE-*`
    entries in SHA256SUMS (`src/sysupdate/sysupdate-resource.c`). Those, or 0.1's signed
    `channels.json`, close the gap.
- **The test** (`ci/test-update`):
  - It boots `latest`'s image and serves the candidate's channel over HTTP on the host
    (10.0.2.2 from QEMU's user network).
  - The old system writes a marker to DATA, runs `systemd-sysupdate update` and reboots.
  - The candidate must find the marker and both snapshots' extensions, and merge its own
    admin image.
  - A unit conditioned on the candidate's `IMAGE_VERSION` then fails every boot of it. After
    three attempts systemd-boot falls back to the old UKI, which finds the marker and its own
    extensions.
  - A `latest` without update artifacts predates sysupdate support; the test then logs
    "SKIPPED" and passes. That is true exactly once: step 6's first cycle. Its second cycle
    upgrades from the first.
- **Findings from bring-up:**
  - The production UKI is installed writable (`Mode=0644`). systemd-boot treats a read-only
    file, which is what `0444` becomes on vfat, as "no boot counting", and never renames it
    (`src/boot/boot.c`). With `0444` the candidate kept booting forever.
  - A boot is good once `boot-complete.target` is reached, and `systemd-bless-boot` then
    removes the counter. The test's failure unit runs late, so the test makes
    `boot-complete.target` require it through a `systemd.unit-dropin.boot-complete.target~…`
    credential. Otherwise the first boot is blessed before it fails.
  - `systemd-sysupdate` lives in `/usr/lib/systemd`, not on `PATH`.

## D53. The kernel checks extension signatures; no userspace fallback

0.0.3, between steps 6 and 7. The owner noticed the fallback's console noise (D50).
- **Before.** Each extension activation first offered the root-hash signature to the kernel.
  The Virt kernel lacked `DM_VERITY_VERIFY_ROOTHASH_SIG` and rejected the table, so systemd
  checked the signature in its own process.
- **Now.** The kernel sets `DM_VERITY_VERIFY_ROOTHASH_SIG` and
  `SYSTEM_TRUSTED_KEYS="certs/verity.crt"`; the Virt kernel element stages the development
  verity certificate into its tree. dm-verity verifies every extension image's signature
  against the built-in trusted keyring, where the kernel logs the certificate at boot
  ("Beamline development verity signing").
- **Fallback off.** The signed command line carries `systemd.allow_userspace_verity=0`, so the
  kernel's check is the only path. `/usr/lib/verity.d` stays; systemd still uses it to pick
  the certificate.
- **Trade-off.** As with module signing (security §19.4), the kernel of every channel now
  trusts the development verity key. That is acceptable only while no production deployments
  exist. Stage 3 embeds a production certificate instead.
- `ci/test-extensions` passes unchanged: the tampered and unsigned copies are refused and the
  signed images merge. The "Unrecognized verity feature" lines are gone.

## D54. Human accounts are systemd-homed users on LUKS2 with btrfs

0.0.3 step 7 (spec rev 6 §18.3). Replaces D27's credential-defined dev account.
- **Kernel.** `DM_CRYPT`, `CRYPTO_XTS`, `CRYPTO_AES` (with `CRYPTO_AES_ARM64_CE_BLK` on arm64),
  `CRYPTO_USER_API_SKCIPHER` (cryptsetup encrypts keyslot areas through it), `BTRFS_FS` and its
  POSIX ACLs. Loop devices were already there.
- **Base.** homed, homework, userdbd and `pam_systemd_home` come with systemd. FDSDK's
  `system-auth` and `password-auth`, which the login and GDM stacks include, already carry
  `pam_systemd_home`, and systemd's own `systemd-user` and `systemd-run0` stacks do too. The
  base adds FDSDK's btrfs-progs for `mkfs.btrfs`. The presets enable `systemd-homed`,
  `systemd-homed-firstboot` and `systemd-userdbd.socket`; the dev account's
  userdb-credential units are gone.
- **Accounts come from credentials.** `systemd-homed-firstboot` runs `homectl firstboot` on the
  first boot (D45 made first boots real), which creates every `home.create.<user>` record.
  `tools/qemu-test.py` passes dev (uid 60001, in `wheel`) and alice (uid 60002, no groups).
  Each record carries:
  - LUKS storage with btrfs and a fixed size;
  - `enforcePasswordPolicy: false`, since the test passwords equal the user names;
  - a light argon2id PBKDF (64 MiB, 100 ms) so a 2 GB VM boots quickly;
  - both `secret.password` and `privileged.hashedPassword`: homework refuses a record without
    a hashed password ("User record has no hashed passwords, refusing").
- **No automatic login.** homed authenticates every activation, so GDM's `custom.conf` no longer
  sets `AutomaticLogin`. The greeter lists Alice, then Developer. `ci/test-desktop` signs dev
  in with QMP keystrokes (`qemu-test.py --type`: Down, Enter, the password, Enter), 35 and 42
  seconds after GDM starts.
- **The desktop check** waits for `/run/user/60001/bus` with a timer that retries every
  5 seconds, under `ConditionPathExists=`, instead of a path unit. logind mounts a fresh tmpfs
  over `/run/user/<uid>`, so the bus socket appears below the path unit's inotify watch and
  never triggers it.
- **First boots take longer.** The home areas are created before `systemd-user-sessions`, which
  moved the boot markers. The admin check had been ordered only after the admin extension,
  and printed its marker before `BEAMLINE_SELINUX_OK` (integration 20261009.1449 failed on
  that). Like the other test units, it is now also ordered after `beamline-boot-ok.service`.

## D55. Locked root, polkit in the base, run0 as confined admin

0.0.3 step 8 (spec rev 6 §18.1, §19; security §9.4). Decided with the owner: run0 is the only
escalation, polkit decides who, a confined SELinux domain decides what.
- **Root.** `/usr/lib/sysusers.d/00-beamline-root.conf` defines
  `u root 0 "Super User" /root /usr/bin/nologin`. It sorts before systemd's `basic.conf`, so
  this definition wins. sysusers sets an invalid password (`!*`). `u!` (v257) would also
  expire the account, and then `pam_unix` refuses the account phase of run0's root sessions
  ("account root has expired"); the first run0 attempt hung on exactly that.
  `image/root-virt.bst` checks the result when the image is built: UID 0, shell
  `/usr/bin/nologin` (from shadow), and a password field starting with `!`. `debug-shell.service` is masked in SYSTEM (`/etc/systemd/system`
  symlink to `/dev/null`), so the `systemd.debug_shell` option opens no root shell either.
- **polkit** is FDSDK's, now in the base (`base/security.bst`) instead of the desktop stack.
  - Its authentication helper is socket-activated (`polkit-agent-helper.socket`), so nothing
    depends on a setuid bit BuildStream cannot carry.
  - `image/root-virt.bst` deletes `pkexec`, as it does `su`, and the extension build excludes
    it. `check-policy.py` rejects `pkexec` and `doas` beside `su` and `sudo` in every artifact.
  - Rules live only in SYSTEM (`/usr/share/polkit-1/rules.d/10-beamline.rules`). duktape's
    JavaScript never comes from a mutable location.
  - polkit's tmpfiles rule is masked (`/etc/tmpfiles.d/polkit-tmpfiles.conf` linked to
    `/dev/null`). It creates `/etc/polkit-1/rules.d` as `0750 root:polkitd` to protect
    administrator-written rules. On Beamline that directory is empty and read-only, and the
    unprivileged image build cannot chown.
  - Administrators are `unix-group:wheel`. For `org.freedesktop.systemd1.manage-units` (run0,
    and systemctl start/stop) and the sysupdate actions, members of wheel get
    `AUTH_ADMIN_KEEP` and everyone else gets `NO`: no prompt for an administrator's password.
- **What nologin does and does not do.** Root's nologin shell closes console and other logins.
  It does not stop a bare `run0`: run0 without a command starts the caller's `$SHELL` as root
  (`src/run/run.c`), not root's account shell. The plan, and spec rev 6's first wording of
  §19, assumed otherwise; §19 is corrected. An administrator can therefore open a root shell,
  which is the "confined admin" the owner chose: only wheel gets through polkit, and every run0
  session, shells included, runs in `admin_t`, which Stage 1 confines.
- **run0's domain.** systemd's own `systemd-run0` PAM stack (`/usr/lib/pam.d`) runs
  `pam_selinux`. `seusers` maps root to `admin_u`, and `default_contexts` gives the session
  started from `init_t` the context `admin_r:admin_t`. The policy adds `admin_u`, `admin_r`
  and `admin_t` under a P2 attribute, `beamline_admin_domain`. Like `user_t`, `admin_t` has no
  rules in Stage 0: its denials are recorded, and Stage 1 confines it (security §9.4). The
  `setenforce`/`load_policy` neverallow already covers it.
- **The test** (`ci/test-run0`) drives the serial console with a script
  (`qemu-test.py --serial-script`, which matches prompts that end without a newline):
  - dev's `run0` asks for dev's password, then the command runs as UID 0 in
    `admin_u:admin_r:admin_t`;
  - a bare `run0` opens dev's own shell as root, also in `admin_t`;
  - alice's `run0` gets "Access denied", and `pkcheck` refuses her the sysupdate action;
  - a root console login fails.

## D56. Scoped mutable /etc: merged in the initrd, rebuilt from the allowlist

0.0.3 step 9 (spec rev 6 §14, security §9.5). The design is the owner's, revised once during
the step.
- **Merged in the initrd.** The first version merged the layer in the host. PID 1 reads the
  static hostname and the locale at startup, before any host confext refresh, so those
  settings had to leave the allowlist. The owner then chose to merge in the initrd instead:
  - systemd's own `systemd-confext-sysroot.service` runs in the initrd (`image/initrd-virt.bst`
    adds it to `initrd.target.wants`). Its drop-in runs `systemd-confext --root=/sysroot
    refresh --mutable=yes` with the signed-only image policy.
  - It needs DATA, so two initrd mount units, `sysroot-data.mount` (DATA read-write at
    `/sysroot/data`) and `sysroot-var.mount` (the `/var` bind), come before it. They are not
    fstab `x-initrd.mount` entries: `initrd-parse-etc` adds those after
    `initrd-root-fs.target`, and the stock merge unit runs before that target. The mounts move
    to the host at switch-root.
  - The host's `systemd-confext.service` still refreshes `/etc` with the same layer and the
    linked confext images (D50). Every refresh after the initrd's merge logs the kernel
    warning `overlayfs: upperdir is in-use`. systemd builds the new overlay in a private
    namespace before it unmounts the old one, which shares the upper directory. Afterwards
    exactly one overlay is on `/etc` (checked on snapshot 20261009.1803).
- **First-boot growth** is unchanged: the host's systemd-repart grows the mounted DATA
  partition, and `systemd-growfs@data` (from fstab, ordered after repart) grows the mounted
  filesystem.
- **The allowlist**: `hostname`, `machine-info`, `localtime`, `adjtime`, `locale.conf`,
  `vconsole.conf` and `machine-id`.
- **The merge is scoped.** DATA is not verity-protected. A file put into the layer by an
  offline edit of the disk, or written during a permissive development boot, would otherwise
  become part of `/etc`: a unit, a PAM stack, a polkit rule. SELinux governs only writes on a
  running enforcing system.
  - `beamline-etc-allowlist.service` therefore rebuilds the layer before every merge, with
    `systemd-tmpfiles --inline` and no shell: copy each allowlisted file aside (`C-`, missing
    files skipped), remove the layer (`R`), recreate it (`d`), copy the files back.
  - Copies made in the initrd carry no SELinux label. The host relabels the seven paths
    (`10-data-labels.conf` `z` lines, with file contexts for the layer's paths).
- **SELinux is the second layer.**
  - The allowlisted files have their own types: `hostname_etc_t`, `timezone_etc_t`,
    `locale_etc_t` and `machine_id_etc_t`. systemd labels the files it creates from these
    contexts.
  - `etc_t`, `shadow_t`, `selinux_config_t`, `usr_t`, `bin_t` and `init_exec_t` form
    `beamline_immutable_file_type`. `kernel-cil.py` gives platform domains everything on
    every other type. On immutable types, in the file classes, they may only read, execute
    and (directories) add or remove entries, which a service needs to replace its own file.
  - The policy's neverallows forbid every domain to create, write, rename, unlink, link,
    setattr or relabel files and symlinks of immutable types, or to create, remove, rename or
    reparent their directories. secilc checks this at compile time.
  - Directory-entry rights on `/etc` still let a platform domain add a file of a mutable type
    there; the next boot's rebuild removes it. Stage 2 gives the settings services their own
    domains and takes those rights from the rest.
- **The machine ID** (replaces D45). SYSTEM ships `/etc/machine-id` as `uninitialized`.
  - On the first boot PID 1 overmounts a transient ID, and the stock
    `systemd-machine-id-commit` writes it into the layer. A drop-in orders the commit after
    the host's confext refresh.
  - Later boots get it from the initrd's merge. The project's initrd machine-ID units and the
    tmpfiles copy are gone.
- **Other writers.** The image ships `/etc/.updated` with the staged files' timestamp.
  Otherwise `ConditionNeedsUpdate=/etc` would become true once `/etc` is writable, and ldconfig,
  sysusers and hwdb-update would write into the layer (and be removed again at the next boot).
- **Trust.** The allowlisted files remain unauthenticated input, parsed by platform services.
  Security §9.2 allows that, since validated input never gains platform provenance.
  Authenticating DATA itself (dm-integrity, TPM-sealed keys) is a Stage 4 evaluation.
- **The test** (`ci/test-settings`):
  - The first boot sets hostname, location, timezone and locale, adds `/etc/beamline-forbidden`
    (permissive lets it into the layer), and reboots.
  - The second boot must have the kernel hostname already set by PID 1, the other settings
    back, and no `beamline-forbidden` in `/etc` or the layer.

## D57. Image elements work in the sandbox's tmpfs

Build infrastructure, no spec change. Image builds were slow because of where they wrote, not
what they ran.
- **The cause.**
  - The builder's buildbox-casd stages every sandbox root through buildbox-fuse, a userspace
    FUSE filesystem. It does so whenever buildbox-fuse is installed: the runner's
    `--staging-mode=default` prefers FUSE.
  - Image elements did their scratch work in `/work` on that root, so every intermediate tree
    and image went through FUSE, and was then hashed into the CAS as action output.
  - Measured on the desktop-gnome extension, against the same steps in RAM:

    | Step | FUSE root | RAM |
    |---|---|---|
    | copy of the 3.5 GB merged tree | 36 s | 14 s |
    | split into sysext/confext trees | 46 s | 13 s |
    | repart (EROFS, verity, signature) | 101 s | 7 s |

    Capturing the output added 39 s. The builder disk's btrfs zstd compression costs only
    about 30% on writes.
- **The change.**
  - The sandbox's `/tmp` is a tmpfs: no FUSE, never captured. `include/image/scratch.yml`
    sets `%{image-scratch}` (`/tmp/work`). `include/extension.yml`, `image/system-virt.bst` and
    `image/initrd-virt.bst` build intermediate trees and images there; only the finished
    images are installed into `%{install-root}`.
  - `image/disk-virt.bst` stays on the FUSE root. The builder's kernel labels files in its
    tmpfs with the builder's own SELinux context, and `mkfs.ext4 -d` copies every extended
    attribute into DATA: the image then carried the build host's label
    (`unconfined_u:object_r:user_tmp_t:s0`, "not valid" under Beamline's policy). EROFS images
    are unaffected because mkfs.erofs labels from the file contexts, and cpio carries no
    attributes. Files on the FUSE root carry none.
  - The desktop extension applies its presets to the staged `/tree` itself instead of a copy.
- **Result.**

  | Element | Before | After |
  |---|---|---|
  | desktop-gnome | 4:14 | 1:26 |
  | SYSTEM | 59 s | 21 s |
  | initrd | 49 s | 34 s |
  | admin | 47 s | 35 s |

  The extension and SYSTEM images came out byte-identical.
- **Memory.** Scratch lives in RAM while an element builds. The desktop extension's peak is
  about 4.3 GB (the split trees and the image); the builder VM has 31 GB.
- **Labels.** Anything built from a scratch tree into a filesystem that copies extended
  attributes picks up the builder's labels. Use scratch only where the label comes from the
  file contexts or the format stores none.
- **Reproducibility.**
  - Comparing the images found that the initrd recorded the build time as the mtime of every
    directory its trimming changed, so no two builds of the initrd or the UKIs matched.
    `image/initrd-virt.bst` now clamps timestamps to `SOURCE_DATE_EPOCH` before packing; two
    builds of the initrd and UKIs are now identical.
  - One nondeterminism remains, and it predates this change. FDSDK's `mkfs.vfat` stamps the
    volume-label entry with the current time and ignores `SOURCE_DATE_EPOCH`, so 2 bytes
    differ in the ESP and in XBOOTLDR between builds.
- **Rejected.** A `buildbox-run` wrapper with `--staging-mode=copy-or-link` would also avoid
  FUSE, for every element. It changes Layer 0 (§31.3), and hardlink staging lets a build that
  writes a staged file in place corrupt the CAS object it is linked to.

## D58. Stage 1 policy, still permissive

0.0.3 step 10 (security §16). The policy is now organised by integrity level, and every VM
test ends with zero unexpected denials. It is still permissive; step 11 enforces it.

- **Seeing every denial first.**
  - The Stage 0 manifests were incomplete. `beamline-avc-report.service` printed the denials
    once, at boot, so nothing from a later session reached the console: not the run0 test,
    not the desktop test's own login. The 473 recorded denials were the greeter's and the
    boot's.
  - The report now writes a journal cursor, and `beamline-avc-follow.service` continues from it
    for the rest of the boot. `tools/qemu-test.py` reads the console for two more seconds after
    a test's result is known.
  - The follow unit's first version was wanted by `multi-user.target` without being ordered
    after it. systemd orders a target after the units it wants, and the report is ordered after
    the target, so this was a cycle, which systemd broke by skipping the follow unit in every
    permissive boot. The first permissive runs therefore looked nearly clean. One boot with
    `enforcing=1` showed what they had missed: login shells could not enter `user_t`, and the
    homes were unlabelled (below). The follow unit is now ordered after `multi-user.target`, and
    the harness fails a boot on `Ordering cycle found`, like a failed unit.
- **Structure.**
  - `policy.cil` holds the attributes, types, named transitions and assertions.
  - `platform.cil`, `admin.cil` and `user.cil` hold the domains.
  - `kernel.cil` (generated) holds the classes and the platform domains' broad rules.
  - `handleunknown deny`: `kernel.cil` declares the kernel's full class map, and the
    userspace object managers' classes (dbus, service, systemd's system permissions) are
    declared.
- **Platform domains.**
  - `kernel_t` and `init_t`, plus `hostnamed_t`, `timedated_t` and `localed_t` (the settings
    writers), `sysupdate_t` (systemd-sysupdate and systemd-sysupdated), `homed_t`
    (systemd-homed and systemd-homework) and `sysext_t` (systemd-sysext and
    systemd-confext), each entered from `init_t` through its executable's type.
  - Other services stay in `init_t` until Stage 2. Every platform domain keeps the Stage 0
    rules, except that it may never execute content a lower level can write.
- **`sysext_t`, not in the plan.**
  - Stage 0's records showed the merges writing SYSTEM types. Building a merged hierarchy
    gives the mutable layer's root on DATA `etc_t`, the `/usr` metadata in the tmpfs workspace
    `usr_t`, and makes overlayfs probe the work directory with files of those types. D56's
    assertions forbade all of that to every domain.
  - The merger is now the one domain exempt from them. It is also the overlays' mounter, so
    overlayfs performs copy-up on DATA with its credentials, after checking the writing
    process's.
  - The overlay the initrd mounts has no mounter label until the policy loads, so it counts as
    `kernel_t` until the host's refresh replaces it.
  - When overlayfs copies a file up it also sets the upper parent directory's timestamps, with
    the mounter's credentials. So the mounters, `sysext_t` and `kernel_t`, are the only domains
    that may set attributes on immutable directories. Creating, removing, renaming or relabelling
    one remains the merger's alone.
- **The root of `/etc`'s layer.** It is the merged `/etc`'s root, so its label decides what a
  process creating a file directly in `/etc` gets. The initrd creates it before any policy is
  loaded, and systemd-confext relabels it only when it merges an extension. Without one, `/etc`
  stayed `unlabeled_t` all boot, and confined domains could not search it. The initrd's rebuild
  now sets `etc_t` itself with a tmpfiles `t` line: until a policy is loaded, root may set any
  label.
  - The base tests masked `systemd-confext.service` to keep the extensions out, so they never
    ran the host's refresh of `/etc` that production boots run. They mask
    `beamline-extensions-link.service` instead, as `ci/test-settings` already did.
- **Untrusted content.**
  - `beamline_untrusted_type` covers DATA's types, homes, `/tmp`, `/run` (with
    `/run/user/<uid>` as `user_runtime_t`), `tmpfs_t` (`/dev/shm`, memfds), the ESP, the settings
    files and unlabelled files.
  - A neverallow keeps platform and admin domains from executing any of it.
- **Filesystem labels.**
  - EROFS is `system_fs_t`, ext4 and btrfs `data_fs_t`, overlay `overlay_fs_t`. btrfs had no
    `fsuse` rule before, so the homed homes were unlabelled.
  - SYSTEM code types (all immutable types but `etc_t`) may associate only with the EROFS,
    overlay and tmpfs labels, and a neverallow forbids `data_fs_t`. Whatever label a process
    chooses, an executable labelled as platform code cannot be created on DATA.
- **`admin_t`** (P2, run0) may:
  - read the system and execute SYSTEM code;
  - manage units through PID 1 (the `service` class);
  - reach the platform's D-Bus and varlink services and the journal;
  - change the allowlisted settings, and its own temporary and runtime files.

  Assertions keep it from:
  - `sys_module`, `sys_rawio`, `mac_admin` and `mac_override`;
  - module loading and `execmem`;
  - writes to `/proc`, `/sys` and the other kernel interfaces, where a tunable can name a
    usermode helper the kernel runs;
  - raw block device writes;
  - mounting, and mounts over SYSTEM's types;
  - tracing platform processes.
- **`user_t`** (P0) is free with its own data (homes, `/tmp`, its runtime directory, memfds,
  the greeter's directories), its processes, user namespaces and the mounts inside them. It
  reads and executes the system and talks to the platform through sockets, D-Bus and PID 1's
  status. It keeps `execmem` (security §8.4); its user manager's BPF probes are dontaudited
  (security §11).
- **Homes.** systemd-homework creates each home's btrfs without labels, so a home's root was
  `unlabeled_t`, and everything a session created below it inherited that.
  - A `user@.service` drop-in relabels the mounted homes' roots from the file contexts
    (`z /home/*`) as root before the user manager starts: `user_home_dir_t`.
  - Type transitions make what `user_t` creates below a home's root `user_home_t`.
  - `%h` cannot be used there: in a system unit it is the service manager's home, `/root`.
- **Entering `user_t`.** pam_selinux gives login's shell and GDM's session `user_t` through
  `bin_t`, and the user manager through `init_exec_t`; both are entrypoints.
- **Writability probes.** Services ask access(2) whether a file is writable; fwupd, for one,
  asks about its configuration and then changes its mode. On immutable types the answer is no
  in an enforcing boot, so platform and admin domains `dontaudit` the `audit_access` checks on
  them. Writes themselves are still audited. fwupd's configuration ships 0640, the mode it
  insists on.
- **Labels that were wrong.**
  - PID 1 labels the cgroup directories it creates from the file contexts. Without an
    entry they were `default_t`; `/sys/fs/cgroup` is now `cgroup_t`.
  - `/dev/shm` was `device_t`.
  - `/data/...` paths had no contexts below the top directories.
  - The homed images (`/home/<user>.home`) matched the home directory entry. They are
    `data_t` now.
  - pidfs had no label.
  - GDM creates `/var/lib/gdm` and `/run/gdm` itself, so named type transitions give them
    `xdm_var_lib_t` and `xdm_runtime_t`.
  - Named transitions also give the allowlisted settings, `/etc/.pwd.lock` (systemd-firstboot)
    and `/etc/.updated` (systemd-update-done) their types whoever creates them. The last two
    are `etc_runtime_t`, which the next boot's rebuild drops.
- **Services that wrote `/etc`.**
  - `ldconfig.service` is masked in SYSTEM. systemd-sysext stamps the merged `/usr` with
    the merge time, so `ConditionNeedsUpdate=/etc` held on every boot with an extension, and
    ldconfig rewrote `/etc/ld.so.cache`. The root's cache is built with the image and each
    extension's confext carries its own (D36), so nothing needs it at runtime.
  - CUPS keeps its state and both configuration files on DATA. cupsd writes its ServerRoot
    (queues, PPDs, certificates) and the printcap, and corrects `cupsd.conf`'s and
    `cups-files.conf`'s ownership to root:lp, which the image cannot carry (D31).
    `cups-files.conf` sets `ServerRoot /var/lib/cups` and the printcap there. tmpfiles copies
    both files to `/var/lib/cups` once, and a drop-in runs cupsd with those copies.
    Configuration changes made with cupsctl persist; changes to the image's defaults reach
    only new installations.
  - colord's unit had `ConfigurationDirectory=colord`, which made systemd create
    `/etc/colord`. A drop-in resets it.
- **Expected denials.**
  - `policy/selinux-expected.toml` lists the denials the negative tests are expected to
    provoke, each with its test and reason. It is empty until step 11.
  - `tools/integrate.py` records the unexpected denials in the manifest (`unexpected`) and
    reports their number. Step 11 makes any unexpected denial fail a cycle.
  - The update test also boots the previous snapshot, whose denials are its own. In that log
    only the candidate's boots count: each boot starts at the kernel banner, and the test
    unit names the version it booted.
- **Tests.**
  - `tests/vm/run0.script` now has dev's run0 actually administer: restart a unit, set the
    hostname through hostnamed, read the journal.
  - The script matches the login prompt for any hostname.
  - `ci/test-update` skips a `dev` candidate. Outside a cycle the candidate's version sorts
    before every snapshot (digits sort after letters), so sysupdate finds nothing newer.
- **Open: `systemd-run` from wheel runs in `init_t`.**
  - run0 asks PID 1 for a transient unit, and so does `systemd-run`. Both need `system start` on
    PID 1, and polkit sees the same action (`manage-units`, verb start) with the same unit
    naming (`run-p<pid>-i<inode>`).
  - Only run0 adds a PAM session, which is what gives `admin_t`. A wheel user who may use run0
    can therefore start a transient service without PAM, which runs as root in `init_t`, a
    platform domain. Neither SELinux nor polkit can tell the requests apart today.
  - Closing this needs PID 1 to bound every transient unit a session requests: no context
    higher than the caller's unless PAM assigns one. The owner decided on a downstream systemd
    patch, to be proposed upstream afterwards. A distribution broker was rejected: it would be
    a new privileged service parsing user requests (security §9.2), and it closes nothing
    while PID 1's transient-unit call stays open to sessions. 0.0.3's negative tests cover run0
    itself.

## D59. Stage 1 enforcing, negative tests, denial gating

0.0.3 step 11 (security §15, §16, §19.4, §19.5).
- **Enforcing.**
  - `files/selinux/config` says `SELINUX=enforcing`, so the production UKI enforces. The
    separately signed development UKI boots with `enforcing=0` (security §19.4).
  - `loader.conf` has `editor no`.
  - Secure Boot is still not enforced in QEMU, so a host that controls the firmware can boot
    the development UKI, which is the documented §19.5 limitation.
- **The mode is tested, not assumed.**
  - `ci/boot` injects a unit that reads `/sys/fs/selinux/enforce`, and requires
    `BEAMLINE_SELINUX_ENFORCE=1` on the default boot.
  - `ci/test-boot-entries` requires the production entry to enforce and the development entry
    to be permissive.
- **Gating.** A cycle whose tests pass but which recorded an unexpected denial is recorded as
  failed. The manifest says why, and `ci/integrate` exits non-zero.
- **What enforcing exposed.** The first enforcing run passed everything except the desktop:
  GDM's session never started, and nothing was recorded.
  - Each user manager is an SELinux object manager, like PID 1. It checks the session's requests
    against systemd's `system` and `service` classes: uploading gnome-session's environment, or
    starting D-Bus-activated user services. `user_t` had none of those permissions.
  - A user manager is unprivileged and cannot write audit records, so it logs its denials as
    ordinary journal messages. The report units read only `_TRANSPORT=audit`, so these denials
    never reached the console, in permissive cycles (D58's included) or enforcing ones.
  - The report units now read every transport and print to the console only, so their own
    output cannot come back as input. Kernel denials can then appear twice, through audit and
    through the kernel log; `tools/integrate.py` counts distinct denials.
  - User units now have their own type, `user_unit_file_t` (`/usr/lib/systemd/user`,
    `/etc/systemd/user`; immutable). The session may manage those and its own generated,
    transient and home units, and its user manager itself. PID 1's units keep `usr_t` and
    `etc_t`, on which `user_t` has only `status`, so the same `service` permission does not
    reach system units.
- **Negative tests (`ci/test-security`).**
  - One boot, enforcing. A test unit (root, `init_t`, the harness) merges the admin extension
    for `cp`, `insmod` and `setenforce`. It runs each check through `systemd-run --wait --pipe`
    with the check's own `SELinuxContext=` and `User=`.
  - Checks that must be refused run as root, so that SELinux, not file permissions, is what
    refuses them.

  | Check | Result |
  |---|---|
  | P0 (alice) executes an unsigned ELF it copied to `/var/tmp` | allowed |
  | P0 writes `/usr` | refused (read-only, verity-backed) |
  | P0 and `admin_t` append to `/etc/pam.d/login` | refused (SELinux) |
  | `admin_t` rewrites `/etc/hostname` | allowed |
  | P0 enters `sysupdate_t` or `admin_t` through `/proc/self/attr/exec` | refused (transition) |
  | `sysupdate_t` executes the ELF in `/var/tmp` | refused (execute on `tmp_t`) |
  | `admin_t` runs `setenforce 0` | refused, enforcement stays on |
  | `admin_t` runs `insmod` | refused (`sys_module`) |
  | alice reads dev's active home | refused (DAC: homes are 0700; homed encrypts them at rest) |

  - Covered elsewhere: tampered and unsigned extensions (`ci/test-extensions`), rollback
    (`ci/test-update`), the unauthorized update request (`ci/test-run0`), and the production
    boot's mode (`ci/boot`).
  - Deferred, as security §15 says:
    - the Python script, since no artifact ships an interpreter. (Wrong: the base shipped
      Python 3.14 through GLib's developer tools. Corrected in D60.)
    - privileged BPF, since none ships BPF tooling;
    - `beamlinectl`, the updater's library and script loading, and containers.
- **Expected denials.** `policy/selinux-expected.toml` lists the 11 denials these tests provoke.
  Two come from `ci/test-settings`'s deliberate write outside the allowlist; nine from
  `ci/test-security`, including the capability checks of the P0 checks that run as root.
  Nothing else may deny.
- **Not closed.** A wheel member can still reach `init_t` through `systemd-run` (D58, security
  §9.4).

## D60. 0.0.4 direction: an interpreter-poor base, POSIX extensions, setuid-free

Spec revision 7, security revision 4. The owner set the direction after a reality check of the
0.0.3 images and two rounds of questions. Recorded here: the decisions, the facts they rest on,
and where the owner chose between alternatives.

**Facts from the reality check (snapshot 20261009.2312)**
- The base had Python 3.14 and `libpython`. gnome-build-meta's `sdk/glib.bst`, carried in
  Beamline's FDSDK junction (D28), depends at runtime on `python3-packaging` for GLib's
  developer tools. D59 and security §15 wrongly said no artifact shipped an interpreter.
- The desktop added `gjs`/`gjs-console`, `lua` and `wpexec`, about 125 Python scripts, 84 `sh`
  scripts and 16 `bash` scripts with no bash to run them. It also brought parts of Samba,
  OpenSSH (server pieces included), LVM, iptables, plymouth, pppd and NetworkManager's CLI.
- No artifact had a setuid or setgid file: BuildStream drops the bits (D31), and
  `files/image/permissions` restores none. `fusermount3`, which Flatpak's document portal
  needs, was therefore not setuid either.
- GDM executes the session program directly; it falls back to `/bin/sh` only for a script the
  kernel cannot execute, and only exports `SHELL`. gnome-session is a compiled program, not the
  old wrapper that re-ran itself through the login shell. A login shell that is not a shell
  does not break graphical login.
- os-test measures the C library, headers, system calls and paths. Its utilities suite is
  planned, not written, and it runs over ssh with tests built on the target. Debian (glibc)
  scores about 92%, mostly lost on glibc's headers and functions. The owner dropped it as a
  goal.

**Decisions**
- **Composition.**
  - "Base image" means SYSTEM alone: healthy, not meaningfully interactive.
  - base + desktop is a conventional desktop without a UNIX environment.
  - base + `posix` is a traditional UNIX server; all three together give both.
- **Interpreters.**
  - What matters is interpreters a user can run. Embedded engines that only run system code
    stay: GNOME Shell's SpiderMonkey, polkit's duktape, WirePlumber's Lua.
  - Python leaves the base. `gjs`, `lua` and `wpexec` leave the desktop unless that regresses
    it.
  - Flatpak applications and binaries a user brings to their own home stay allowed:
    uncomfortable, not prohibited.
- **The shell.**
  - The first aim was a base without `/bin/sh`. It conflicted with rule 17: `posix-devel` and
    the printing extension need a shell, as do Xwayland's session scripts and Flatpak's
    triggers. The owner chose to keep `dash` in the base as `/bin/sh`, so the goal is no
    interactive login shell.
  - The initrd gets no shell.
  - `login`'s empty-shell fallback, `systemd-run --shell` and `sulogin` may stop working in
    the base.
- **The login shell.**
  - `/usr/libexec/beamline-shell` is a stub written in C (the project's first runtime code)
    and listed in `/etc/shells`.
  - Interactively it prints how to get a shell and exits. As an interpreter it fails non-zero.
  - It is systemd-homed's built-in default (`-Ddefault-user-shell`). Root keeps nologin. Users
    may switch to `/usr/bin/bash`. Test accounts keep `/usr/bin/sh`.
- **`posix`.**
  - It replaces the admin extension: mostly the same contents, named and made explicit.
  - **Utilities:** POSIX.1-2024 mandatory plus User Portability. Excluded: XSI-only, SCCS,
    UUCP, and utilities needing a daemon or privilege (`at`, `batch`, `crontab`, `mailx`,
    `talk`, `write`, `mesg`, `newgrp`). The goal is a userspace defined by an external
    specification, not a UNIX.
  - **Order of preference:** uutils, including sibling projects once they pass their own
    suites, then GNU, then others. uutils is preferred even where it deviates from POSIX.
  - **Extras:** `bash` (`/usr/bin/bash`), `mandoc` with the POSIX manual pages, and a named set
    of system tools POSIX does not define. Base tools no service needs move here.
- **`posix-devel`** replaces devel: POSIX C and software development, plus toolchains.
- **`printing-scanning`.**
  - CUPS, its filters and backends, SANE and HPLIP; `lp` exists only there.
  - The desktop keeps `libcups`. Avahi joins the base.
- **The desktop.**
  - GNOME Shell extension support is removed at build time. `desktop-gnome-advanced` comes later
    as a conflicting alternative with more customization.
  - The SSH server, LVM, iptables, plymouth, pppd and NetworkManager's CLI leave it. Samba
    stays.
- **Toggles.**
  - Only administrators toggle extensions, and 0.0.4 has no toggle tool.
  - Persistence comes later with a daemon and `beamlinectl`. The GUI never offers disabling
    the desktop, and `beamlinectl` disables it only while `posix` is enabled.
- **Setuid-free.**
  - No setuid, setgid or file-capability binaries, except `fusermount3`, the sole exception
    until upstream's setuid-free FUSE.
  - No `newgrp`. Rootless containers' ID mapping goes through privileged services.
- **`systemd-run`.** The downstream patch (D58) is the last 0.0.4 step.
- **Later.** `desktop-kde`.

**0.0.4 steps** (spec §39; one green frozen cycle each, then a HEAD integration):
1. Python out of the base.
2. The stub shell.
3. `posix` replaces admin.
4. `printing-scanning`.
5. Desktop interpreters and Shell extensions.
6. Desktop pruning.
7. The setuid audit and FUSE.
8. `posix-devel`.
9. The `systemd-run` patch.
10. A HEAD integration.

**Section numbers.** Spec §39 is new; former §39–§43 are now §40–§44. Live references in AGENTS
and security were updated; revision-history entries keep the numbers of their own revision.
