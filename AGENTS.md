# AGENTS.md

Instructions for coding agents (and humans) working in this repository.

## What this is

Beamline is an image-native, immutable Linux OS built from source with
BuildStream 2 on top of Freedesktop SDK, using systemd for as much of the OS framework as
possible. There is no package manager on the installed system; every change produces a new
image.

Its identity is the release model (§17): track upstream development HEADs (FDSDK `master`,
Linux `master`, systemd `main`, ...), resolve them to an exact source set, build and test the
whole image, and publish only green **snapshots**. `latest` and `edge` are pointers to
immutable snapshots that move by evidence. There are no separate source tracks,
and promotion never rebuilds anything.

- [docs/spec.md](docs/spec.md) is the authoritative specification (revision 6). Cite it as `§N`.
- [docs/security.md](docs/security.md) is its normative security annex: a Biba-style mandatory
  integrity hierarchy (P0 user code … P3 platform) on SELinux. Cite it as `security §N`.
- [docs/release-model.md](docs/release-model.md) is the rationale for the release model.
- [docs/decisions.md](docs/decisions.md) records deviations and interpretations made while
  implementing. If a change departs from the spec, add an entry there in the same change.

Vocabulary: **integration** = one attempt to build the current HEADs (ephemeral);
**snapshot** = a green integration (immutable, `snapshot-YYYYMMDD.HHMM`); **checkpoint** =
a snapshot kept forever; **pin** = a temporary, visible exception in `policy/tracking.toml`;
**HEAD conformity** = tracked components at their designated HEAD (e.g. `3/4`).

## Current milestone

0.0.1 (§36) and 0.0.2 (§37) are done. 0.0.2 delivered, one green integration cycle per step:
1. read-only root preparation (build-time users, credential-defined dev account);
2. EROFS SYSTEM-A + DATA;
3. SELinux-capable kernel and userspace;
4. SELinux Stage 0: CIL policy with MCS, labelled images, Virt permissive, AVCs recorded
   (security §16);
5. the extension pipeline (EROFS sysext + confext) and the admin sysext (uutils);
6. the gnome-build-meta wiring;
7. the `desktop-gnome` extension;
8. the automated desktop test.

Current milestone: 0.0.3 (§38, D43), one green integration cycle per step:
1. a stable machine ID, saved on DATA and bound in by the initrd;
2. development keys (`files/keys/dev`), signed UKIs, module signing;
3. dm-verity SYSTEM, root hash in the signed UKI;
4. XBOOTLDR, A/B SYSTEM slots, RECOVERY and the RecoveryOS stub, the development UKI, boot
   counting;
5. signed, verity-protected extensions, coupled to their snapshot;
6. systemd-sysupdate following a signed channel directory, with upgrade and rollback tests;
7. systemd-homed accounts (LUKS + btrfs);
8. locked root with a nologin shell, polkit in the base, run0 as confined admin;
9. scoped mutable `/etc` (system settings, scoped by SELinux);
10. SELinux Stage 1 policy, still permissive, until no unexpected AVCs remain;
11. Stage 1 enforcing, negative tests, AVC gating.

0.0.3 is done: steps 1 to 11, each proven by a frozen cycle, then the HEAD integration
`snapshot-20261009.2312` (7/7 at HEAD, enforcing, no unexpected denials).

Out of scope until later milestones: NetworkManager, the Hardware image, Secure Boot
enforcement (UKIs are signed, but QEMU tests do not enforce it), a real RecoveryOS (a stub
until further notice), Qt/LXQt, the Server profile and self-hosted builds (deferred, around
version 3).

Structural repository changes stay one experimental dimension at a time (§35). Develop
frozen, then integrate HEAD (D49): each package step is verified by `./ci/integrate --frozen`
(every tracked component stays at `latest`'s commits, so the cache is reused). When a package
is complete, a plain `./ci/integrate` moves all tracked HEADs together, as a step of its own.

Status: see the "Status" section at the end of this file.

## Repository map

| Path | Responsibility |
|---|---|
| `project.conf`, `project.refs`, `junction.refs` | BuildStream project; source pins live in `project.refs`, junction pins in `junction.refs` (written by integration cycles) |
| `include/` | Shared YAML: URL aliases, `snapshot.yml` (snapshot id, `dev` outside integration), kernel source and build rules (`include/kernel/`) |
| `elements/junctions/` | Freedesktop SDK and BuildStream plugin junctions |
| `elements/base/` | The smallest bootable userspace shared by every profile (§5) |
| `elements/overrides/` | FDSDK element overrides: components tracked at their own upstream HEAD, and SELinux-aware rebuilds |
| `elements/security/` | The SELinux policy and its build-only tools (secilc, setfiles) |
| `elements/admin/` | Admin extension content (uutils coreutils, maintenance tools) |
| `elements/extensions/` | Extension images: a composed tree per extension, then EROFS sysext/confext images |
| `elements/kernel/` | Project-owned kernels and their config-fragment element |
| `elements/profiles/` | Profile stacks (`virt.bst` now, `hardware.bst` at 0.1) |
| `elements/image/` | Root tree, initrd, UKI and disk image composition |
| `elements/tests/` | Tests that run inside BuildStream |
| `tests/vm/` | Units injected into VM tests through credentials (never in an image) |
| `files/` | OS configuration: units, presets, tmpfiles, PAM, networkd, kernel fragments, repart, the SELinux policy (`files/selinux`), the image permission list, the committed development keys (`files/keys/dev`, DEVELOPMENT ONLY) |
| `policy/` | `tracking.toml` (designated branches, selection, pins) and policy allowlists |
| `ci/` | The canonical build/test/integration workflow (portable shell) |
| `tools/` | Python helpers: `integrate.py`, `check-policy.py`, `qemu-test.py`, `build-extension.py` |
| `lima/` | Builder VM definition for Apple Silicon hosts |
| `.github/workflows/` | Thin hosted orchestration that only calls `ci/` |

## Where things run

- **macOS host**: editing, `./ci/*` entry points, and booting images with QEMU + HVF.
  Outputs land in `out/` (gitignored): `out/<arch>/virt/` for the current image,
  `out/snapshots/` and `out/integrations/` for integration results.
- **Lima VM `myos-builder`** (Fedora 44, created by `./ci/bootstrap`): every `bst`
  invocation. `ci/` scripts delegate there automatically via `limactl shell`. The repo is
  mounted at the same path; the BuildStream cache stays on the VM's own disk.
- **Linux CI runners / the VM itself**: the same `ci/` scripts run directly.

Never run `bst` on macOS. Never point BuildStream caches or kernel build trees at a macOS
shared directory (§23).

## Commands

```bash
./ci/bootstrap      # once: create/start the builder VM and install BuildStream
./ci/check          # seconds: static checks (policy, Python, YAML, shellcheck)
./ci/build          # bst build image/disk-virt.bst (or: ./ci/build <element.bst>)
./ci/build-kernel   # kernel only
./ci/test-base      # base policy test inside BuildStream
./ci/image          # build + check out out/<arch>/virt/disk.raw
./ci/boot           # boot the base (extensions masked), wait for BEAMLINE_SELINUX_OK, BEAMLINE_BOOT_OK
./ci/test-reboot    # boot twice: the machine ID saved on DATA survives, journalctl -b -1 works
./ci/test-verity    # corrupt SYSTEM-A in the overlay: dm-verity must refuse it
./ci/test-boot-entries  # three boots: production (default), development (enforcing=0), RecoveryOS stub
./ci/test-update    # boot `latest`, sysupdate to the candidate's channel over HTTP, then roll back
./ci/test-run0      # serial console: dev's run0 runs in admin_t, alice is refused, root cannot log in
./ci/test-settings  # two boots: allowlisted /etc settings persist, anything else written to /etc does not
./ci/test-security  # enforcing: the negative tests (P0, admin_t, the updater; policy/selinux-expected.toml)
./ci/test-extensions  # boot again, merge the admin extension on demand, use it
./ci/test-desktop   # boot with a virtual GPU: GNOME session, PipeWire, portal, Flatpak, screenshot
./ci/test-all       # all of the above, in order
./ci/integrate      # one integration cycle: resolve HEADs, test-all, record the snapshot
tools/qemu-test.py --image out/aarch64/virt/disk.raw --interactive   # serial login: dev/dev or alice/alice
tools/qemu-test.py --image out/aarch64/virt/disk.raw --interactive --gpu 2d --memory 4G  # GNOME window
QEMU_SYSTEM=/path/to/virgl/qemu-system-aarch64 tools/qemu-test.py --image out/aarch64/virt/disk.raw \
    --interactive --gpu gl --memory 4G   # accelerated (virglrenderer QEMU, e.g. a UTM build)
```

Ad-hoc BuildStream from macOS: `limactl shell --workdir "$PWD" myos-builder -- bst <args>`.

`ci/integrate` options: `--frozen` (development cycle at `latest`'s source set, D49),
`--force` (integrate even if nothing changed), `--no-commit` (on green, do not commit the
refs or tag `snapshot-<id>`).

## Hard rules

These are architectural invariants (§42). A change that breaks one is wrong even if it builds.

1. **No package manager, no DKMS** in any image (§2.1). `/usr` is generated, not administered.
2. **Exact sources, tracked HEADs (§2.3, §31).** Every source has an immutable ref in
   `project.refs` (junction elements: `junction.refs`). Tracked components follow
   `policy/tracking.toml`: an element's `track:` must equal its designated branch, and its
   ref changes only through `ci/integrate` (`tools/integrate.py resolve`). To hold a
   component back, add a `pin` with `reason` and `issue` to the policy. Never hand-edit a
   ref silently and never substitute an older commit for a broken HEAD (§17.2).
3. **Reuse order for FDSDK components (§2.2):** source-ref override first; junction element
   override only when the build rules or tracking branch must change (`elements/overrides/`);
   project-owned element only for distribution policy (kernel, image composition, identity,
   configuration). Everything else follows FDSDK `master`.
4. **Bash stays out of the base (§6).** `/usr/bin/sh -> dash`. Anything needing bash or
   coreutils at runtime belongs in a sysext (`admin`, `devel`) — not in `base/`.
   **Coreutils that ship anywhere are uutils, as one multicall binary (§7.2).** GNU coreutils
   is allowed only as a build-time tool that never reaches an artifact
   (`image/integration-tools.bst`).
5. **No shell in base unit files (§6).** No `sh -c`, pipes, `&&`, `||`, `$()` in `Exec*=`.
   Enforced by `tools/check-policy.py` (`./ci/check` and `tests/base-policy.bst`). Shell in
   BuildStream *build* commands is fine; it never reaches the image.
6. **Kernel config:** only fragments in `files/kernel/config/` are committed. The resolved
   `.config` is a build artifact (`/usr/lib/modules/<release>/config`). The Virt kernel is
   configured from `allnoconfig` (§11.4): a feature exists only if a fragment asks for it,
   including menus that normally default to on. A requested symbol that configuration
   drops fails the build — fix the dependency, don't delete the check.
7. **Kernel, initrd and UKI are separate elements (§13). The initrd is project-owned and
   built from the image's own tree; never use dracut** (`check-policy.py` rejects it).
8. **CI logic lives in `ci/`.** Workflow YAML only calls `ci/` scripts (§26).
9. **Tests never modify artifacts.** VM tests boot a throwaway qcow2 overlay (§28).
10. **No credentials in images.** Root stays locked. Human accounts are systemd-homed users,
    never in the image: `tools/qemu-test.py` passes `home.create.dev` (wheel) and
    `home.create.alice` records, which `systemd-homed-firstboot` creates on the first boot
    (D54). Test passwords equal the user names.
11. **Native builds only.** The image architecture equals the builder architecture.
12. **Layer 0 stays boring (§31.3).** BuildStream, buildbox, the builder VM and the plugin
    junctions are pinned and change only deliberately, never inside an integration cycle.
13. **Promotion never rebuilds (§17.3).** A snapshot's bytes never change; only pointers move.
14. **Integrity boundaries (security §2, §17).** Platform (P3) code never executes mutable
    code: no helpers, libraries, scripts or plugins from DATA or user-controlled paths, no
    shell evaluation of input, no dynamic code. Running trusted code never elevates its caller,
    and a signature is evidence, not authority. SELinux labels come from the policy's
    `file_contexts` when filesystem images are created; BuildStream cannot carry them
    (security §19.1).
15. **No web engine in any artifact (§7.1, security §8.2).** WebKitGTK, JavaScriptCoreGTK and
    Chromium/CEF never enter SYSTEM, the initrd, a UKI or an extension; web content runs in
    Flatpak. Build components without their optional web views (D29).
16. **`/etc` is read-only except its allowlist (§14, D56).** Only the files in
    `beamline-etc-allowlist.service` may change at runtime, through the mutable confext layer
    that the initrd rebuilds from that allowlist at every boot; SELinux types scope the writes.
    Users come from build-time sysusers or homed, configuration from the image or a confext.
17. **Extensions depend only on the base image (§8, D51).** Never on another extension: no
    dependency graph, no layering. Extensions may be mutually exclusive alternatives.
18. **run0 is the only escalation (§18.1, §19, D55).** su, sudo, pkexec and doas never ship
    (`check-policy.py` rejects them). Root has an invalid password and a nologin shell; polkit
    lets only wheel through run0, and run0 sessions run in `admin_t`.
19. **The production boot enforces, and denials gate (security §15, §16, D59).** A cycle with a
    denial not listed in `policy/selinux-expected.toml` is red. Only a negative test may add an
    entry there; any other denial is fixed in the policy, the labels or the component.

## How to verify a change

| Change touches | Run at least |
|---|---|
| anything | `./ci/check` |
| `elements/`, `include/`, `files/`, `project.*` | `./ci/build` (or the specific element) |
| kernel, initrd, UKI, repart, units, presets, os-release | `./ci/image && ./ci/boot` |
| base composition | `./ci/test-base` |
| before calling a milestone done | `./ci/test-all` |
| a package step (structural change) | `./ci/integrate --frozen` (a green frozen snapshot is the proof) |
| tracked inputs, `policy/tracking.toml`, or a completed package | `./ci/integrate` (a green HEAD snapshot is the proof) |

Report what was run and what failed. A kernel build takes tens of minutes; a cached
rebuild of the image takes a few.

## BuildStream conventions

- FDSDK elements are referenced through the junction:
  `junctions/freedesktop-sdk.bst:components/systemd.bst`.
- `project.conf` includes FDSDK's `include/runtime.yml`, so FDSDK variables (`%{prefix}`,
  `%{indep-libdir}`, `%{datadir}`, ...) are available. Project variables: `%{os-id}`,
  `%{os-name}`, `%{os-version}`, `%{arch}`, `%{efi-arch}`, `%{kernel-arch}`,
  `%{serial-console}`.
- Image-building `script` elements take tools from the sandbox root (FDSDK
  `runtime-gnu`, systemd, ...) and stage the OS tree at `/sysroot` as data. Never stage the
  OS tree at `/` next to `runtime-gnu`: bash's `/usr/bin/sh` would overlap dash's.
- `manual` elements without FDSDK build stacks need `strip-binaries: ''`.
- `overlaps` and `unaliased-url` are fatal warnings. Add URL aliases to `include/aliases.yml`.
- New files carry an `SPDX-License-Identifier` header. Element names follow §34.
- Overrides of FDSDK elements live in `elements/overrides/` and are wired in through
  `config.overrides` in `elements/junctions/freedesktop-sdk.bst`. An override is a copy
  of FDSDK's recipe: its dependencies carry the `junctions/freedesktop-sdk.bst:` prefix,
  FDSDK's `target_arch` conditions become `arch`, the tracked git source comes first in
  `sources:`, and a header records the FDSDK commit it was copied from.
- Keep structural changes focused; component updates arrive through integration cycles.

## Gotchas

- FDSDK 26.08 `runtime-minimal` has no coreutils or bash. At runtime there is no `echo`,
  `cat`, `grep`, `sed`: units must use systemd facilities (the boot marker uses
  `systemd-escape`).
- FDSDK artifacts should be **pulled** from `cache.freedesktop-sdk.io`. FDSDK is selected
  as the newest `master` commit whose upstream pipeline passed (§31.1), so its artifacts
  exist. If `bst build` starts compiling glibc or GCC, the junction options or cache
  configuration have drifted from FDSDK's defaults — stop and fix that instead of waiting
  hours.
- Linux comes as GitHub's archive of the selected master commit (about 270 MB, D32), not as a
  git fetch: `git_repo` re-downloads most of a repository's history whenever a tracked branch
  moves, which for `linux.git` cost 3.3 GB and 49 minutes per cycle. Other tracked
  project-owned git sources use the classic `git` source (C git, incremental fetches, D33);
  FDSDK's elements keep `git_repo`, which is cheap for their fixed refs.
- Overrides copy FDSDK recipes and drift when FDSDK changes them. When a tracked FDSDK
  update touches an overridden recipe, re-copy it and re-apply the documented changes.
- FDSDK integration commands assume coreutils/gzip. They run with a temporary toolbox that
  `image/root-virt.bst` strips again (docs/decisions.md D12). A new integration command
  needing more tools goes into `image/integration-tools.bst`. Use `bootstrap/*`
  variants: anything whose runtime closure contains bash collides with dash on
  `/usr/bin/sh` (the `overlaps` fatal warning catches it).
- The initrd is a trimmed copy of the root (D6). Anything that must not run in the initrd
  has to stay out of it; failures there use up the host's start-rate limits.
- BuildStream artifacts keep only the executable bit: every other file arrives 0644 and every
  directory 0755, owned by root, without setuid bits or capabilities. Elements that create
  filesystems restore modes from `files/image/permissions` on a copy of the tree
  (`include/image/permissions.yml`, D31). Add an entry there when a file needs a mode.
- Files created with mode 0000 (e.g. `/etc/shadow` from sysusers) are unreadable to the
  unprivileged build sandbox; chmod them before packing.
- The sandbox root is staged through buildbox-fuse: everything written there is slow and is
  hashed into the CAS as action output. Elements that build images do their scratch work in
  `%{image-scratch}` (`/tmp/work`, a tmpfs; `include/image/scratch.yml`, D57) and install only
  the finished images. Not where a filesystem copies extended attributes (DATA's ext4): files in
  the builder's tmpfs carry the builder's SELinux label.
- When a boot misbehaves and login is impossible, inject a debug unit as a credential
  (`systemd.extra-unit.<name>.service` over SMBIOS, see `credential_args()` in
  `tools/qemu-test.py`) that runs `journalctl`/`systemctl --failed` with
  `StandardOutput=tty`.
- SYSTEM is built in three stages (D47): `image/system-virt.bst` makes the EROFS image and its
  verity hash tree with `systemd-repart --split`, `image/uki-virt.bst` puts the root hash in the
  command line, and `image/disk-virt.bst` copies the split images in. dm-verity needs
  device-mapper's udev rules (`base/device-mapper.bst`); without them activation hangs.
- Updates (D52): `image/update-virt.bst` makes a snapshot's channel directory (UKIs, SYSTEM and
  its verity tree named by UUID, extension images, signed SHA256SUMS); `ci/image` checks it
  out to `out/<arch>/virt/update`, and a green cycle publishes it under
  `out/snapshots/<id>/update` with `out/channels/latest` pointing at it. `ci/test-update` needs
  a `latest` that has update artifacts, and skips otherwise. The production UKI must stay
  writable on XBOOTLDR: systemd-boot never counts boots of a read-only file.
- The initrd mounts DATA read-write (`sysroot-data.mount`, `sysroot-var.mount`) and merges
  `/etc`'s mutable layer before switch-root (D56). A setting outside the allowlist written into
  `/etc` survives only until the next boot; adding one means extending the allowlist unit, the
  file contexts and the tmpfiles relabels together. Every later confext refresh (the host's
  `systemd-confext.service`, `beamline-admin`) logs the kernel warning `overlayfs: upperdir is
  in-use`: systemd mounts the new overlay before it unmounts the old one, which shares the
  upper directory. Exactly one overlay remains on `/etc` afterwards.
- QEMU on macOS has no vhost-vsock. Host↔guest test channels on macOS need another
  transport (serial, virtio-serial, or forwarded SSH).
- systemd refuses system extensions stored under `/usr` (overlayfs `ELOOP`). Extension images
  live on DATA, one set per snapshot, in `/var/lib/beamline/{extensions,confexts}/<name>_<snapshot>.raw`;
  units link the set built with the booted SYSTEM (`%A`) into `/run/extensions` and
  `/run/confexts` (D50). Only signed verity images merge: an extension built without the
  verity key, or a tampered one, is refused.
- gnome-build-meta's recipes depend directly on its `sdk/*` elements (glib, gtk, pango, ...).
  Beamline's FDSDK junction carries gbm's overrides of those FDSDK components; without them two
  copies would overlap (D28).
- GNOME is built locally, against Beamline's FDSDK. A systemd or FDSDK move rebuilds the
  systemd-dependent part of GNOME. Run such builds in the background.
- FDSDK's shadow strips `pam_selinux` from its PAM files. Beamline's own PAM stacks add it back.
- SELinux labels exist only in filesystem images (security §19.1). To see contexts on a
  running system without coreutils, read `/proc/<pid>/attr/current` from dash
  (`read -r c < /proc/1/attr/current`). The audit AVC records also name the file contexts.
- The policy's classes and initial SIDs are generated from the kernel's headers
  (`kernel/selinux-headers.bst`, D35). Never add kernel classes to the CIL by hand.
- The policy is split by integrity level (D58): `policy.cil` (types, attributes, named
  transitions, assertions), `platform.cil`, `admin.cil`, `user.cil`; `kernel-cil.py` generates
  the platform domains' broad rules. A service gets its own domain through an executable type,
  a `typetransition` from `init_t` and a file context. Platform and admin domains can never
  execute `beamline_untrusted_type` content, and only `sysext_t` may write SYSTEM's types:
  secilc refuses a rule that breaks either assertion.
- Denials reach the serial console twice over: `beamline-avc-report` prints the boot's,
  `beamline-avc-follow` the rest. `tools/integrate.py` classifies them against
  `policy/selinux-expected.toml`; a denial a negative test provokes must be listed there with
  its reason, any other is unexpected. Services that write `/etc` at runtime show up as `init_t`
  denials on `etc_t`: move their state to DATA (as for CUPS, D58) rather than allowing it.
- Junction refs must be in `junction.refs`: BuildStream reads them in its first loading
  pass (plugins, includes from junctions), before `project.refs` exists for it.
- `limactl shell` does not forward environment variables; pass values as arguments.
- `tools/integrate.py` needs the builder (bst, git, zstd, ruamel.yaml); `ci/integrate` runs it
  there. An interrupted cycle leaves `out/integrations/current`: close it with
  `tools/integrate.py record --result aborted`, which restores the refs files.
- `tools/qemu-test.py` fails a boot on any systemd `[FAILED]` or `[DEPEND]` status line, not
  only on panics: green means healthy, not just "reached the marker".

## Status

**HEAD conformity 7/7** (2026-10-10). `latest` is `snapshot-20261009.2312`, the HEAD integration
that closes 0.0.3:

| Component | Tracking | Selected |
|---|---|---|
| Freedesktop SDK | `master` (newest CI-green) | `8090132` (26.08rc.2+355) |
| gnome-build-meta | `master` (newest CI-green; GNOME recipes, D28) | `d3baf29` (49-branchpoint+1331) |
| Linux | `master` (GitHub archive of the commit, D32) | `9a06d4b` |
| systemd | `main` (overrides: trimmed, SELinux; classic git source) | `v262-384-g570c468` (runs as `263~devel`) |
| dash | `master` (classic git source) | `v0.5.13.5` (master = tag) |
| uutils | `main` (admin extension) | `0.12.0-380-g7bc1eb6` |
| SELinux userspace | `main` (build-time policy tools only) | `3.11-267-g5e0e5c8` |

Beamline boots under QEMU/HVF to `BEAMLINE_BOOT_OK` in about 6 s, with no `[FAILED]` units.
The root is SYSTEM-A, read-only EROFS (`/etc` included) under dm-verity, its root hash in the
signed UKI's command line (D47). systemd-sysupdate installs a newer snapshot from a signed
channel directory into the free slot, with boot counting and rollback (D52). The disk has the 0.0.3 layout (ESP, XBOOTLDR with production,
development and RecoveryOS stub UKIs, SYSTEM-A/B, reserved RECOVERY, DATA; D48), and state
lives on DATA: `/data`
(ext4, grown to the disk at first boot), with `/var` and `/home` bind-mounted from it. Users are
created at build time; human accounts are systemd-homed users (LUKS2 with btrfs on DATA),
created on the first boot from the test tool's `home.create.*` credentials (D54). `/etc` is
read-only except an allowlist of system settings (hostname, machine-info, timezone, locale,
keymap, machine ID) in a mutable confext layer on DATA, which the initrd rebuilds from the
allowlist and merges before PID 1 starts (D56). SELinux Stage 1 enforces on the production
boot (D58, D59); the development UKI is permissive. Platform domains (`init_t`, the settings
services, `sysupdate_t`, `homed_t`, `sysext_t`) never execute content a lower level can write,
run0 sessions run in a confined `admin_t`, and sessions (login, GDM, the user manager) in
`user_t`. SYSTEM-A is labelled by mkfs.erofs, the homed homes when their user manager starts.
Every denial of every VM test is recorded in the manifest and classified against
`policy/selinux-expected.toml`; a cycle with an unexpected one is red. `ci/test-security` runs
the negative tests (D59). The
desktop-gnome extension (GNOME Shell, GDM, Settings, Nautilus, File Roller,
Software, PipeWire, portals, Flatpak) merges from DATA at boot, as a signed verity image built
with this snapshot (D50); `ci/test-desktop` checks
the session and keeps a screenshot. The admin extension (bash, uutils, tools) merges on
demand (`systemctl start beamline-admin`). `systemctl is-system-running` reports `running`, networkd DHCP and resolved DNS
work, and the base has no bash, coreutils, su or pkexec (`sh -> dash`). Root cannot log in;
run0 is the only escalation: polkit lets wheel through after the user's own password and
refuses everyone else, and run0 sessions run in `admin_u:admin_r:admin_t` (D55). homed and the sysupdate timer
are preset-disabled: updates run when asked (`systemd-sysupdate update`). The Virt kernel is narrow: allnoconfig plus fragments, an 11 MB Image, no
modules, and only modules signed with the development key could load (D46). The UKI and
systemd-boot are signed with the development Secure Boot key; Secure Boot is not enforced.

Snapshots are committed and tagged only on a clean tree. Until the release-model work is
committed, green cycles publish to `out/snapshots/` without tags.

Cost: a cycle that only touches image assembly takes about 10 minutes (the desktop image
alone is 3.5). A new Linux commit adds about 1 minute of archive download and 2 minutes of
kernel build. A systemd move rebuilds systemd and everything above it, including the
systemd-dependent part of GNOME: 172 elements in 35.5 minutes. A gnome-build-meta or FDSDK
move rebuilds the GNOME parts it touches locally (GNOME is built against Beamline's FDSDK,
D28).

Open items, in rough order:
- util-linux's SELinux support (D30), if enforcement needs it.
- Upstream reports:
  - `git_repo` re-downloads history when tracking a branch (D32);
  - `cargo2` cannot load without a ref under `project.refs` (D36);
  - gjs/mozjs do not declare readline (D38).
- Polkit, fusermount3 and other files that need ownership, setuid or capabilities. They
  run today because Stage 0 is permissive and nothing exercised them, but `chmod` in the
  sandbox cannot restore ownership. Build such filesystems from a tar stream with explicit
  metadata (`mkfs.erofs --tar`, D31).
- Integration automation at 0.1: scheduled cycles, publication to GitHub Releases, signed
  channel pointers, retention and promotion tooling (`edge`), and hosted aarch64 +
  x86_64 runs (§17.4, §39). Until then, cycles are run by hand.
- Kernel new-symbol reporting between snapshots (§11.3, §32).
- A wheel member can start a transient unit with `systemd-run` instead of run0, which runs in
  `init_t` instead of `admin_t` (security §9.4, D58). Needs a systemd change or a broker.
- The disk image is not yet bit-reproducible: FDSDK's `mkfs.vfat` stamps the ESP's and
  XBOOTLDR's volume-label entry with the build time (D57). Everything else in it is.
- Owner proposal for a later version, not scheduled: desktop-gnome without GNOME Shell
  extension support, and `desktop-gnome-advanced` as a separate extension with that support.
  The two are alternatives, never layered (D51).
