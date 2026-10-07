# AGENTS.md

Instructions for coding agents (and humans) working in this repository.

## What this is

MyOS (placeholder name) is an image-native, immutable Linux OS built from source with
BuildStream 2 on top of Freedesktop SDK, using systemd for as much of the OS framework as
possible. There is no package manager on the installed system; every change produces a new
image.

- [docs/spec.md](docs/spec.md) is the authoritative specification. Cite it as `§N`.
- [docs/decisions.md](docs/decisions.md) records deliberate deviations and interpretations.
  If a change departs from the spec, add an entry there in the same change.

## Current milestone: 0.0.1 (spec §36)

Goal: a clean checkout produces a bootable AArch64 Virt image inside the Linux builder VM,
and that image boots under QEMU/HVF on Apple Silicon, printing `MYOS_BOOT_OK`.

In scope: FDSDK runtime-minimal, systemd, dbus-broker, dash, kmod, networkd, resolved,
project-owned Virt kernel, systemd-based initrd, UKI, QEMU virt + UEFI, serial console.

Out of scope until later milestones: desktop, NetworkManager, the Hardware image, homed,
SELinux enforcement, Secure Boot, A/B updates, sysupdate, dm-verity, EROFS root (0.0.2).

Introduce one experimental dimension at a time (§35). Do not bump FDSDK, the kernel channel
and the boot chain in the same change.

Status: see the "Status" section at the end of this file.

## Repository map

| Path | Responsibility |
|---|---|
| `project.conf`, `project.refs`, `junction.refs` | BuildStream project; source pins live in `project.refs`, junction pins in `junction.refs` |
| `include/` | Shared YAML: URL aliases, kernel source channels (`include/kernel/*.yml`) and build rules |
| `elements/junctions/` | Freedesktop SDK and BuildStream plugin junctions |
| `elements/base/` | The smallest bootable userspace shared by every profile (§5) |
| `elements/kernel/` | Project-owned kernels and their config-fragment element |
| `elements/profiles/` | Profile stacks (`virt.bst` now, `hardware.bst` at 0.1) |
| `elements/image/` | Root tree, initrd, UKI and disk image composition |
| `elements/tests/` | Tests that run inside BuildStream |
| `files/` | OS configuration: units, presets, sysusers, tmpfiles, networkd, kernel fragments, repart |
| `policy/` | Source/release policy and policy allowlists |
| `ci/` | The canonical build/test workflow (portable shell) |
| `tools/` | Python helpers: `check-policy.py`, `qemu-test.py` |
| `lima/` | Builder VM definition for Apple Silicon hosts |
| `.github/workflows/` | Thin hosted orchestration that only calls `ci/` |

## Where things run

- **macOS host**: editing, `./ci/*` entry points, and booting images with QEMU + HVF.
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
./ci/boot           # boot it under QEMU, wait for MYOS_BOOT_OK
./ci/test-all       # all of the above, in order
tools/qemu-test.py --image out/aarch64/virt/disk.raw --interactive   # serial login: dev/dev
```

Ad-hoc BuildStream from macOS: `limactl shell --workdir "$PWD" myos-builder -- bst <args>`.

## Hard rules

These are architectural invariants (§42). A change that breaks one is wrong even if it builds.

1. **No package manager, no DKMS** in any image (§2.1). `/usr` is generated, not administered.
2. **Exact sources.** Every source has an immutable ref in `project.refs` (junction
   elements: `junction.refs`). Branches/globs in `track:` are only for discovering updates:
   `bst source track <element>`, review, commit.
3. **Reuse order for FDSDK components (§2.2):** source-ref override first; junction element
   override only when the build rules must change; project-owned element only for
   distribution policy (kernel, image composition, identity, configuration).
4. **Bash stays out of the base (§6).** `/usr/bin/sh -> dash`. Anything needing bash or
   coreutils at runtime belongs in a sysext (`admin`, `devel`) — not in `base/`.
5. **No shell in base unit files (§6).** No `sh -c`, pipes, `&&`, `||`, `$()` in `Exec*=`.
   Enforced by `tools/check-policy.py` (`./ci/check` and `tests/base-policy.bst`). Shell in
   BuildStream *build* commands is fine; it never reaches the image.
6. **Kernel config:** only fragments in `files/kernel/config/` are committed. The resolved
   `.config` is a build artifact (`/usr/lib/modules/<release>/config`). A fragment symbol
   that `olddefconfig` drops fails the build — fix the dependency, don't delete the check.
7. **Kernel compilation and UKI generation are separate elements (§13).**
8. **CI logic lives in `ci/`.** Workflow YAML only calls `ci/` scripts (§26).
9. **Tests never modify artifacts.** VM tests boot a throwaway qcow2 overlay (§28).
10. **No credentials in images.** Root stays locked. The prototype `dev` account gets its
    password at boot through a systemd credential (`tools/qemu-test.py --interactive`).
11. **Native builds only.** The image architecture equals the builder architecture.

## How to verify a change

| Change touches | Run at least |
|---|---|
| anything | `./ci/check` |
| `elements/`, `include/`, `files/`, `project.*` | `./ci/build` (or the specific element) |
| kernel, initrd, UKI, repart, units, presets, os-release | `./ci/image && ./ci/boot` |
| base composition | `./ci/test-base` |
| before calling a milestone done | `./ci/test-all` |

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
- Keep changes focused: one component (or cohort, §31) per update (§32).

## Gotchas

- FDSDK 26.08 `runtime-minimal` has no coreutils or bash. At runtime there is no `echo`,
  `cat`, `grep`, `sed`: units must use systemd facilities (the boot marker uses
  `systemd-escape`).
- FDSDK artifacts should be **pulled** from `cache.freedesktop-sdk.io`. If `bst build`
  starts compiling glibc or GCC, the junction options or cache configuration have drifted
  from FDSDK's defaults — stop and fix that instead of waiting hours.
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

## Status

0.0.1 primary success criterion met (2026-10-07). On an M3 Max, a clean checkout builds
`image/disk-virt.bst` in the Lima builder, and the image boots under QEMU/HVF to
`MYOS_BOOT_OK` in about 6.5 s, with `systemctl is-system-running` = `running`, zero failed
units, networkd DHCP and resolved DNS working, `dev` serial login, no bash, no coreutils, no
su, and `sh -> dash`. `./ci/test-all` passes.

The first build takes about an hour: roughly 45 minutes downloading FDSDK artifacts
from cache.freedesktop-sdk.io, plus about 12 minutes compiling the kernel. A few small FDSDK
elements missing from the aarch64 cache build locally (dbus-broker, dracut, systemd-ukify,
cpio). After the bring-up iterations the VM's BuildStream cache is about 19 GB. Cached
image rebuilds take a few minutes.

Open items, in rough order:
- x86_64 image and hosted CI builds (0.1); `ci/` is ready, workflows run only `ci/check`.
- Kernel new-symbol reporting (§11.3) and `tools/update-*.py` automation (0.1).
- Unused heavy dependencies in the systemd closure (curl, libmicrohttpd, ...); trim with
  FDSDK source-ref or element overrides when there is a measured reason.
- BuildStream drops setuid bits and file capabilities; restore them in image assembly
  when something in the base needs them (nothing does yet).
