# MyOS (fdsdk-linux-experiment)

An experimental, image-native Linux OS: a small immutable systemd host built from exact
source revisions with [BuildStream 2](https://buildstream.build/) on top of
[Freedesktop SDK](https://freedesktop-sdk.io/), with no package manager on the installed
system, separate Hardware and Virt profiles, and desktop/admin/devel tooling delivered as
system extensions. "MyOS" is a placeholder name.

- Specification: [docs/spec.md](docs/spec.md)
- Decisions and deviations: [docs/decisions.md](docs/decisions.md)
- Working in this repo (people and agents): [AGENTS.md](AGENTS.md)

Current milestone: **0.0.1**, a bootable AArch64 Virt image under QEMU.

## Quick start (Apple Silicon macOS)

Requirements: [Lima](https://lima-vm.io/) and QEMU (`brew install lima qemu`).

```bash
./ci/bootstrap
```

```bash
./ci/test-all
```

`ci/bootstrap` creates the `myos-builder` Fedora VM where all BuildStream work happens.
`ci/test-all` runs static checks, builds the image, runs the base policy test, checks
out `out/aarch64/virt/disk.raw` and boots it with QEMU/HVF until it prints `MYOS_BOOT_OK`.

To poke at a booted system on the serial console (user `dev`, password `dev`, injected at
boot as a systemd credential):

```bash
tools/qemu-test.py --image out/aarch64/virt/disk.raw --interactive
```
