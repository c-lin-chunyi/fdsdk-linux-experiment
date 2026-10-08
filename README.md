# Beamline

An experimental, image-native Linux OS: a small immutable systemd host built from exact
source revisions with [BuildStream 2](https://buildstream.build/) on top of
[Freedesktop SDK](https://freedesktop-sdk.io/), with no package manager on the installed
system, separate Hardware and Virt profiles, and desktop/admin/devel tooling delivered as
system extensions.

- Specification: [docs/spec.md](docs/spec.md)
- Decisions and deviations: [docs/decisions.md](docs/decisions.md)
- Working in this repo (people and agents): [AGENTS.md](AGENTS.md)

Releases are **snapshots of upstream HEADs**. An integration cycle resolves FDSDK `master`,
Linux `master`, systemd `main` and the other tracked components to exact commits. It then
builds and boots the whole image, and publishes it only if everything is green.
`latest-green`, `edge` and `stable` are pointers to those immutable snapshots
([release model](docs/release-model.md), spec §17).

Status: 0.0.1 done (a bootable AArch64 Virt image under QEMU), with every tracked input at
its upstream HEAD.

## Quick start (Apple Silicon macOS)

Requirements: [Lima](https://lima-vm.io/) and QEMU (`brew install lima qemu`).

```bash
./ci/bootstrap
```

```bash
./ci/test-all
```

To run one integration cycle (resolve HEADs, build, test, record a snapshot under
`out/snapshots/`):

```bash
./ci/integrate
```

`ci/bootstrap` creates the `myos-builder` Fedora VM where all BuildStream work happens.
`ci/test-all` runs static checks, builds the image, runs the base policy test, checks
out `out/aarch64/virt/disk.raw` and boots it with QEMU/HVF until it prints `BEAMLINE_BOOT_OK`.

To poke at a booted system on the serial console (user `dev`, password `dev`, injected at
boot as a systemd credential):

```bash
tools/qemu-test.py --image out/aarch64/virt/disk.raw --interactive
```
