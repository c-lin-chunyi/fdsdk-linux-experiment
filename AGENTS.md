# AGENTS.md

Instructions for coding agents (and humans) working in this repository.

## What this is

Beamline is an image-native, immutable Linux OS built from source with
BuildStream 2 on top of Freedesktop SDK, using systemd for as much of the OS framework as
possible. There is no package manager on the installed system; every change produces a new
image.

Its identity is the release model (§17): track upstream development HEADs (FDSDK `master`,
Linux `master`, systemd `main`, ...), resolve them to an exact source set, build and test the
whole image, and publish only green **snapshots**. `latest-green`, `edge` and `stable` are
pointers to immutable snapshots that move by evidence. There are no separate source tracks,
and promotion never rebuilds anything.

- [docs/spec.md](docs/spec.md) is the authoritative specification (revision 2). Cite it as `§N`.
- [docs/release-model.md](docs/release-model.md) is the rationale for the release model.
- [docs/decisions.md](docs/decisions.md) records deviations and interpretations made while
  implementing. If a change departs from the spec, add an entry there in the same change.

Vocabulary: **integration** = one attempt to build the current HEADs (ephemeral);
**snapshot** = a green integration (immutable, `snapshot-YYYYMMDD.HHMM`); **checkpoint** =
a snapshot kept forever; **pin** = a temporary, visible exception in `policy/tracking.toml`;
**HEAD conformity** = tracked components at their designated HEAD (e.g. `3/4`).

## Current milestone

0.0.1 (§36) is done: a bootable AArch64 Virt image under QEMU/HVF. Current work: moving the
inputs to their tracked HEADs (§35) and running integration cycles. Next milestone: 0.0.2
(§37): EROFS SYSTEM-A + DATA, desktop directory sysext, admin sysext.

Out of scope until later milestones: desktop, NetworkManager, the Hardware image, homed,
SELinux enforcement, Secure Boot, A/B updates, sysupdate, dm-verity, XBOOTLDR, RecoveryOS
(a pure stub until further notice).

Structural repository changes stay one experimental dimension at a time (§35). Integration
cycles are different: they move all tracked HEADs together, by design.

Status: see the "Status" section at the end of this file.

## Repository map

| Path | Responsibility |
|---|---|
| `project.conf`, `project.refs`, `junction.refs` | BuildStream project; source pins live in `project.refs`, junction pins in `junction.refs` (written by integration cycles) |
| `include/` | Shared YAML: URL aliases, `snapshot.yml` (snapshot id, `dev` outside integration), kernel source and build rules (`include/kernel/`) |
| `elements/junctions/` | Freedesktop SDK and BuildStream plugin junctions |
| `elements/base/` | The smallest bootable userspace shared by every profile (§5) |
| `elements/overrides/` | FDSDK element overrides for components tracked at their own upstream HEAD |
| `elements/kernel/` | Project-owned kernels and their config-fragment element |
| `elements/profiles/` | Profile stacks (`virt.bst` now, `hardware.bst` at 0.1) |
| `elements/image/` | Root tree, initrd, UKI and disk image composition |
| `elements/tests/` | Tests that run inside BuildStream |
| `files/` | OS configuration: units, presets, sysusers, tmpfiles, networkd, kernel fragments, repart |
| `policy/` | `tracking.toml` (designated branches, selection, pins) and policy allowlists |
| `ci/` | The canonical build/test/integration workflow (portable shell) |
| `tools/` | Python helpers: `integrate.py`, `check-policy.py`, `qemu-test.py` |
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
./ci/boot           # boot it under QEMU, wait for BEAMLINE_BOOT_OK
./ci/test-all       # all of the above, in order
./ci/integrate      # one integration cycle: resolve HEADs, test-all, record the snapshot
tools/qemu-test.py --image out/aarch64/virt/disk.raw --interactive   # serial login: dev/dev
```

Ad-hoc BuildStream from macOS: `limactl shell --workdir "$PWD" myos-builder -- bst <args>`.

`ci/integrate` options: `--force` (integrate even if nothing changed), `--commit` (on green,
commit the refs and tag `snapshot-<id>`; only when asked).

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
10. **No credentials in images.** Root stays locked. The prototype `dev` account gets its
    password at boot through a systemd credential (`tools/qemu-test.py --interactive`).
11. **Native builds only.** The image architecture equals the builder architecture.
12. **Layer 0 stays boring (§31.3).** BuildStream, buildbox, the builder VM and the plugin
    junctions are pinned and change only deliberately, never inside an integration cycle.
13. **Promotion never rebuilds (§17.3).** A snapshot's bytes never change; only pointers move.

## How to verify a change

| Change touches | Run at least |
|---|---|
| anything | `./ci/check` |
| `elements/`, `include/`, `files/`, `project.*` | `./ci/build` (or the specific element) |
| kernel, initrd, UKI, repart, units, presets, os-release | `./ci/image && ./ci/boot` |
| base composition | `./ci/test-base` |
| before calling a milestone done | `./ci/test-all` |
| tracked inputs or `policy/tracking.toml` | `./ci/integrate` (a green snapshot is the proof) |

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
- The first `bst source track` of Linux master fetches the whole `linux.git` history (about
  5 GB at roughly 1.5 MB/s from git.kernel.org) to compute the git-describe ref. The mirror
  is kept in the VM's source cache, and later cycles fetch only new commits.
- Overrides copy FDSDK recipes and drift when FDSDK changes them. When a tracked FDSDK
  update touches an overridden recipe, re-copy it and re-apply the documented changes.
- FDSDK integration commands assume coreutils/gzip. They run with a temporary toolbox that
  `image/root-virt.bst` strips again (docs/decisions.md D12). A new integration command
  needing more tools goes into `image/integration-tools.bst`. Use `bootstrap/*`
  variants: anything whose runtime closure contains bash collides with dash on
  `/usr/bin/sh` (the `overlaps` fatal warning catches it).
- The initrd is a trimmed copy of the root (D6). Anything that must not run in the initrd
  has to stay out of it; failures there use up the host's start-rate limits.
- BuildStream artifacts do not keep setuid bits or file capabilities. Nothing in 0.0.1
  needs them; anything that does must restore them during image assembly.
- Files created with mode 0000 (e.g. `/etc/shadow` from sysusers) are unreadable to the
  unprivileged build sandbox; chmod them before packing.
- When a boot misbehaves and login is impossible, inject a debug unit as a credential
  (`systemd.extra-unit.<name>.service` over SMBIOS, see `credential_args()` in
  `tools/qemu-test.py`) that runs `journalctl`/`systemctl --failed` with
  `StandardOutput=tty`.
- QEMU on macOS has no vhost-vsock. Host↔guest test channels on macOS need another
  transport (serial, virtio-serial, or forwarded SSH).
- Junction refs must be in `junction.refs`: BuildStream reads them in its first loading
  pass (plugins, includes from junctions), before `project.refs` exists for it.
- `limactl shell` does not forward environment variables; pass values as arguments.
- `tools/integrate.py` needs the builder (bst, git, zstd, ruamel.yaml); `ci/integrate` runs it
  there. An interrupted cycle leaves `out/integrations/current`: close it with
  `tools/integrate.py record --result failed`, which restores the refs files.
- `tools/qemu-test.py` fails a boot on any systemd `[FAILED]` or `[DEPEND]` status line, not
  only on panics: green means healthy, not just "reached the marker".

## Status

**HEAD conformity 4/4** (2026-10-08). `latest-green` is `snapshot-20261008.0755`:

| Component | Tracking | Selected |
|---|---|---|
| Freedesktop SDK | `master` (newest CI-green) | `c67967f` (26.08rc.2+353) |
| Linux | `master` | `v7.3-rc6-21-g0c2669a` |
| systemd | `main` (two overrides, trimmed) | `v262-337-g6645aa5` (runs as `263~devel`) |
| dash | `master` | `v0.5.13.5` (master = tag) |

Beamline boots under QEMU/HVF to `BEAMLINE_BOOT_OK` in about 6 s, with no `[FAILED]` units.
`systemctl is-system-running` reports `running`, networkd DHCP and resolved DNS work, and the
base has no bash, coreutils or su (`sh -> dash`). homed and sysupdate are preset-disabled. The
Virt kernel is narrow: allnoconfig plus fragments, an 11 MB Image, no modules.

Snapshots are committed and tagged only on a clean tree. Until the release-model work is
committed, green cycles publish to `out/snapshots/` without tags.

Cost: a cycle that only touches image assembly takes a few minutes. A new Linux commit adds
about 2 minutes of kernel build. A systemd change rebuilds systemd and a handful of FDSDK
reverse dependencies locally (dbus, lvm2/libdevmapper, dbus-broker), about 5 minutes. FDSDK
moves arrive as cache pulls.

Open items, in rough order:
- 0.0.2 (§37): EROFS SYSTEM-A + DATA (`/data`, ext4, bind mounts onto `/var` and `/home`,
  §15), desktop directory sysext, and the admin sysext with uutils multicall (§7.2).
- Integration automation at 0.1: scheduled cycles, publication to GitHub Releases, signed
  channel pointers, retention and promotion tooling (`edge`/`stable`), and hosted aarch64 +
  x86_64 runs (§17.4, §39). Until then, cycles are run by hand.
- Kernel new-symbol reporting between snapshots (§11.3, §32).
- BuildStream drops setuid bits and file capabilities; restore them in image assembly
  when something in the base needs them (nothing does yet).
