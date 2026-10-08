# Immutable Linux OS Development Specification

- Status: Initial development specification
- Target maturity: Experimental / developer-oriented
- Primary architecture: AArch64 and x86-64
- Primary development host: Apple Silicon macOS
- Primary build system: BuildStream 2
- Primary upstream substrate: Freedesktop SDK
- Primary system framework: systemd
- Revision: 3 (2026-10-08)

> This file is the project's authoritative specification. The project owner changes it by
> publishing a new revision. Deviations and interpretations made while implementing it are
> recorded in [decisions.md](decisions.md).

## Revision History

- **Revision 3 (2026-10-08).**
  - The OS is named **Beamline**, and its reverse-DNS prefix is `org.beamline` (§19).
  - DATA is an ext4 filesystem mounted at `/data`; `/data/var` and `/data/home` are
    bind-mounted onto `/var` and `/home` (§14, §15).
  - The Virt kernel is narrowed: built from `allnoconfig` plus explicit fragments, keeping
    module support (§11.4).
  - Base systemd features without a base use are disabled (§5.2).
  - Every green snapshot is recorded in git: a refs commit tagged `snapshot-<id>` (§17.4).
  - An override whose upstream recipe changed fails the integration cycle (§31.4).
- **Revision 2 (2026-10-07).**
  - The release model is rebuilt around tracking upstream HEADs and promoting immutable
    snapshots (§2.2, §11.2, §16, §17, §31, §32). The rationale is in
    [release-model.md](release-model.md).
  - New target disk layout: XBOOTLDR, A/B SYSTEM partitions with verity, RECOVERY and DATA
    (§13–§15, §20).
  - The initrd is project-owned, and dracut is not used (§13).
  - Coreutils shipped in any artifact are uutils, as a multicall binary (§7.2).
  - Milestones are remapped (§35–§39), and the non-goals and invariants are updated (§41, §42).
- **Revision 1.** The initial development specification.

## 1. Project Objective

The project defines a source-built, image-native Linux operating system designed around a small immutable host, systemd-native lifecycle management, reproducible BuildStream composition, optional system extensions, and strongly separated hardware profiles.

The deployed operating system shall contain no traditional package manager and shall not treat the installed root filesystem as a mutable package environment.

The base system shall function as a verified appliance. Graphical desktop software, administrative utilities, development tools, and other nonessential facilities shall exist outside the smallest bootable base whenever practical.

The architecture shall prioritize:

* continuous integration of current upstream development HEADs;
* reproducible source builds;
* immutable system artifacts;
* aggressive use of systemd infrastructure;
* minimal host state;
* atomic updates and rollback;
* narrow privilege boundaries;
* independent desktop and administrative extensions;
* deterministic virtualization support;
* compatibility with modern physical hardware;
* upstream-oriented kernel and userspace testing;
* local CI parity with hosted CI.

## 2. Core Design Principles

### 2.1 The Host Is an Artifact

The installed operating system shall be treated as a generated artifact rather than a mutable package database.

Normal operation shall not include:

* RPM;
* DNF;
* DEB;
* APT;
* Pacman;
* Portage;
* package installation into `/usr`;
* DKMS;
* interactive modification of system libraries.

Changes to the base operating system shall require generation of a new system artifact.

### 2.2 Freedesktop SDK Is a Substrate

Freedesktop SDK shall supply the majority of the common dependency graph, toolchain, libraries, and existing BuildStream component definitions.

Freedesktop SDK shall not define final distribution policy.

Distribution policy shall independently control:

* kernel version;
* systemd version;
* Mesa version;
* desktop stack;
* network stack;
* image layout;
* boot architecture;
* update mechanism;
* security policy;
* extension composition;
* hardware support.

Existing Freedesktop SDK recipes shall be reused wherever possible.

Source-reference overrides shall be preferred over copied recipes.

Element overrides shall be introduced only when newer upstream versions require dependency, configuration, or build-rule changes.

Standalone project-owned elements shall be used for components with distribution-specific policy, particularly Linux kernels and image composition.

Freedesktop SDK shall be consumed at its `master` branch, as one of the tracked upstream HEADs (§31). FDSDK master defines the continuously integrated foundation. Its hundreds of components (glibc, GCC, LLVM, OpenSSL, compression libraries, ...) flow into Beamline with each integration cycle, without per-component Beamline policy. Formal FDSDK releases are upstream milestones, not Beamline release boundaries.

Components that define the project's identity shall be promoted out of that foundation and tracked directly at their own upstream HEAD through element overrides. This applies to systemd now, and to Mesa, PipeWire and others as they enter scope. Linux is project-owned (§11). The FDSDK bootstrap and toolchain graph remains FDSDK's responsibility and shall not be forked.

### 2.3 Exact Sources, Not Moving Builds

Upstream branches shall serve only as update-discovery mechanisms.

Every actual build shall reference exact immutable source revisions.

Examples:

```
systemd:
    track: main
    ref: <exact commit>

Linux:
    track: master
    ref: <exact commit>

Mesa:
    track: main
    ref: <exact commit>
```

Reproducibility shall take precedence over direct dependence on mutable branch heads.

In short:

```
source policy:
    track HEAD

artifact policy:
    pin absolutely everything
```

### 2.4 Systemd as the Operating-System Framework

Systemd shall provide as much common system infrastructure as practical.

Preferred facilities include:

```
systemd
systemd-boot
systemd-stub
systemd-repart
systemd-sysupdate
systemd-sysext
systemd-confext
systemd-networkd
systemd-resolved
systemd-timesyncd
systemd-logind
systemd-userdbd
systemd-homed
systemd-machined
systemd-importd
systemd-nspawn
systemd-vmspawn
systemd-oomd
systemd-tmpfiles
systemd-sysusers
systemd-cryptenroll
systemd-pcrlock
journald
udevd
```

Distribution-specific replacements shall require a clear technical advantage.

## 3. Distribution Profiles

Two primary deployment profiles shall share a common userspace and release identity.

### 3.1 Hardware Profile

The Hardware profile shall target laptops and workstations.

Expected components:

```
NetworkManager
systemd-resolved
iwd
BlueZ
fwupd
linux-firmware
broad kernel configuration
physical GPU support
common Wi-Fi support
Bluetooth support
USB and Thunderbolt support
NVMe and SATA support
common audio hardware
common HID devices
```

The Hardware profile shall favor broad compatibility over minimal footprint.

### 3.2 Virt Profile

The Virt profile shall target QEMU virtual machines.

Expected components:

```
systemd-networkd
systemd-resolved
virtio-focused kernel
virtio-net
virtio-blk
virtio-scsi where useful
virtio-gpu
virtio-input
virtio-rng
virtio-console
virtio-vsock
virtiofs
UEFI/OVMF
```

The Virt profile shall intentionally omit unnecessary physical-device support.

Expected omissions include:

```
linux-firmware
Wi-Fi firmware
Bluetooth firmware
fwupd
ModemManager
Thunderbolt support
physical GPU firmware
large collections of hardware drivers
```

The Virt profile shall serve as the primary deterministic CI and integration-test platform.

## 4. Virtual Hardware Contract

The initial Virt hardware ABI shall target:

```
Architecture:
    AArch64: QEMU virt
    x86-64: Q35

Firmware:
    UEFI / OVMF

Storage:
    virtio-blk
    optional virtio-scsi

Network:
    virtio-net

Graphics:
    virtio-gpu

Input:
    virtio-input
    USB HID fallback

Entropy:
    virtio-rng

Console:
    virtio-console
    serial fallback

Host communication:
    virtio-vsock

Filesystem sharing:
    virtiofs

TPM:
    TPM 2.0 through swtpm when enabled
```

The virtual hardware contract shall remain intentionally narrow.

Support for arbitrary emulated legacy hardware shall not be a goal.

## 5. Base Operating System

### 5.1 Base Definition

The base image shall contain only facilities required for:

* boot;
* hardware discovery;
* persistent-state mounting;
* networking;
* DNS;
* time synchronization;
* authentication infrastructure;
* logging;
* privilege mediation;
* image updates;
* extension activation;
* container execution;
* clean reboot and shutdown.

The base shall boot into a healthy state without any desktop extension.

### 5.2 Expected Base Components

Initial base contents shall approximately include:

```
glibc
dynamic loader
libgcc runtime
libstdc++ runtime where required

systemd
udev
journald
logind
tmpfiles
sysusers
resolved
timesyncd
repart
sysupdate
sysext
confext
machined
nspawn

D-Bus broker
polkit core
PAM
NSS/userdb

kmod
cryptsetup libraries/tools required by boot
verity tooling
minimal util-linux functionality

CA certificates
crypto libraries

dash or equivalent minimal POSIX shell
```

Additional libraries shall enter the base only through demonstrated runtime requirements.

The base systemd build shall leave out features the base does not use: journal-remote and journal-upload, QR-code output, xkbcommon keymap validation, and AppArmor (SELinux is the planned security module, §21). Features that later milestones need stay enabled: TPM2, FIDO2, cryptsetup, and curl for `systemd-sysupdate` downloads.

## 6. Shell and Command-Line Policy

Bash shall not be part of the base image.

A small POSIX-compatible `/bin/sh` shall remain available as a compatibility interface.

Recommended arrangement:

```
/bin -> usr/bin
/usr/bin/sh -> dash
```

The presence of `/bin/sh` shall not imply shell-driven system architecture.

Base systemd units shall not invoke shell pipelines.

CI shall reject base units containing avoidable shell constructs such as:

```
/bin/sh -c
/bin/bash -c
|
&&
||
$()
```

Shell usage shall be restricted to exceptional compatibility cases.

## 7. System Extensions

Three major system-extension classes shall be supported.

### 7.1 Desktop Extension

`desktop.sysext` shall contain the graphical environment and associated graphical runtime.

Possible contents:

```
Mesa
libdrm
Wayland
PipeWire
WirePlumber
Flatpak
xdg-desktop-portal
desktop portal backend
Qt
labwc
LXQt components
notification daemon
graphical polkit agent
file manager
launcher
panel
terminal emulator
fonts
themes
icons
desktop session definitions
```

Final placement of Mesa, Wayland, PipeWire, and Flatpak between base and desktop extension shall remain subject to integration testing.

Early prototypes may place most graphical userspace inside `desktop.sysext` to maximize separation.

### 7.2 Administrative Extension

`admin.sysext` shall provide interactive maintenance tools absent from the normal base.

Expected contents:

```
bash
uutils coreutils (multicall)
grep
sed
awk
findutils
procps
iproute2 extras
ethtool
pciutils
usbutils
strace
tcpdump
lsof
curl
jq
less
file
text editor
filesystem diagnostic tools
```

Normal installations shall not require permanent activation of `admin.sysext`.

Coreutils shipped in any Beamline artifact (this extension, the recovery environment, or any later image content) shall be uutils coreutils. It shall be deployed as a single multicall `coreutils` binary, with one symlink per utility. GNU coreutils may still serve as a build-time tool inside BuildStream sandboxes, as long as it never reaches an artifact.

### 7.3 Development Extension

`devel.sysext` shall support operating-system development and low-level debugging.

Possible contents:

```
compiler
linker
headers
pkg-config
Meson
Ninja
gdb
perf
BPF tooling
systemd headers
Mesa headers
kernel headers
debug symbols
```

Application development shall preferentially occur inside an `nspawn` development machine rather than directly through `devel.sysext`.

## 8. Extension Compatibility

Extensions shall be release-coupled rather than treated as arbitrary packages.

Example:

```
base-42
desktop-42.raw
admin-42.raw
devel-42.raw
```

Compatibility metadata shall use:

```
ID=
VERSION_ID=
SYSEXT_LEVEL=
ARCHITECTURE=
```

BuildStream shall resolve dependencies before extension generation.

The deployed system shall not perform dependency solving.

Desktop extension updates shall normally activate after reboot rather than through live replacement during an active graphical session.

## 9. Desktop Environment

The preferred initial graphical stack shall favor a lightweight Wayland environment.

Initial candidate:

```
labwc
LXQt components
Qt
Wayland
Mesa
PipeWire
WirePlumber
xdg-desktop-portal
Flatpak
```

A complete monolithic desktop environment shall not be required.

The graphical environment shall remain replaceable at the extension level where practical.

The base operating system shall remain independent of a specific graphical toolkit.

## 10. Networking

### 10.1 Hardware Profile

Networking shall use:

```
NetworkManager
systemd-resolved
iwd where appropriate
```

NetworkManager shall provide interactive Wi-Fi, VPN, hotspot, captive-portal, and desktop networking behavior.

### 10.2 Virt Profile

Networking shall use:

```
systemd-networkd
systemd-resolved
```

An initial network definition may resemble:

```
[Match]
Type=ether

[Network]
DHCP=yes
IPv6AcceptRA=yes
```

More restrictive VirtIO matching may replace generic matching after hardware-contract stabilization.

## 11. Kernel Architecture

### 11.1 Kernel Ownership

Linux shall be a project-owned component.

Freedesktop SDK kernel policy shall not dictate final kernel versions.

Kernel builds shall remain reproducible BuildStream artifacts.

### 11.2 Kernel Source

The kernel shall be built from the `master` branch of Linus Torvalds' tree. In each integration cycle (§17) it is resolved to an exact commit, like every other tracked upstream HEAD.

There shall be no separate release, rc or main kernel channels. Upstream tags such as `v7.3-rc4` or `v7.3` are metadata: the snapshot manifest records the nearest tag of the selected commit. They are not release lanes.

```
snapshot-20261008.0600

Linux:
    commit: abcdef
    nearest-tag: v7.3-rc4-218-gabcdef
```

A snapshot that coincides with an interesting upstream tag may be retained as a checkpoint (§17.4).

### 11.3 Kernel Configuration

A common configuration shall feed profile-specific fragments.

```
common.config
      │
      ├── hardware.config
      └── virt.config
```

The same source commit shall normally produce both profile kernels.

Example:

```
Linux commit ABC
    ├── linux-hardware
    └── linux-virt
```

Configuration fragments shall remain human-maintained.

Generated complete `.config` files shall remain build artifacts.

New kernel configuration symbols shall be reported by CI.

### 11.4 Virt Kernel

Critical Virt boot-path support should be built directly into the kernel where practical.

Examples:

```
CONFIG_VIRTIO=y
CONFIG_VIRTIO_PCI=y
CONFIG_VIRTIO_BLK=y
CONFIG_VIRTIO_NET=y
CONFIG_EROFS_FS=y
CONFIG_BLK_DEV_DM=y
CONFIG_DM_VERITY=y
CONFIG_EFI=y
```

The Virt kernel shall be narrow. It is configured from `allnoconfig` plus explicit, human-maintained fragments (common, architecture, Virt), rather than from an architecture defconfig, so everything it contains is there on purpose. The boot path and the virtual hardware contract (§4) are built in. Loadable module support remains for optional features.

### 11.5 Hardware Kernel

The Hardware kernel shall enable broad modular support for:

```
AMD graphics
Intel graphics
Nouveau/NVK kernel support
Wi-Fi families
Bluetooth
USB
Thunderbolt
NVMe
SATA
audio
HID
webcams
SD/MMC
common storage controllers
```

Out-of-tree DKMS operation shall not form part of the deployed-system model.

Required external modules shall be built against exact kernel artifacts during CI.

## 12. Kernel Toolchain

LLVM/Clang shall be the preferred production kernel toolchain unless significant regressions appear.

Typical production build:

```
make LLVM=1
```

GCC builds shall provide secondary compile validation.

Kernel compilation shall occur inside BuildStream.

Host-distribution compilers shall not directly produce final kernel artifacts.

## 13. Boot Architecture

The intended final boot chain shall be:

```
UEFI Secure Boot
        ↓
systemd-boot (ESP)
        ↓
signed UKI (XBOOTLDR)
        ↓
systemd-stub
        ↓
Linux
        ↓
project-owned systemd initrd
        ↓
dm-verity SYSTEM discovery
        ↓
immutable SYSTEM
        ↓
systemd
```

The UKI shall include or reference:

```
kernel
initrd
kernel command line
os-release metadata
systemd-stub
```

The initrd shall be project-owned and assembled from the image's own content: a trimmed copy of the system tree, run by systemd through `initrd.target`. dracut and similar shell-hook initrd generators shall not be used.

Kernel compilation, initrd generation and UKI generation shall remain separate BuildStream stages.

## 14. Root Filesystem

The SYSTEM filesystem (the immutable root and `/usr`) shall be read-only and cryptographically verifiable.

Preferred format:

```
EROFS
+
dm-verity
```

Persistent mutable state shall live outside the SYSTEM image, on the DATA partition (§15).

Primary writable areas:

```
/var                    DATA (/data/var, bind-mounted)
/home                   DATA (/data/home, bind-mounted); systemd-homed images (<user>.home)
runtime state under /run
```

Arbitrary persistent mutation of `/etc` shall be minimized.

`systemd-confext` may provide declarative configuration overlays.

## 15. Disk Layout

Target layout:

```
GPT
├─ ESP                      systemd-boot
├─ XBOOTLDR
│  ├─ Beamline current UKI
│  ├─ Beamline previous UKI
│  └─ RecoveryOS UKI        a stub for now (§20)
│
├─ SYSTEM-A                 EROFS
├─ SYSTEM-A-VERITY
├─ SYSTEM-B                 EROFS
├─ SYSTEM-B-VERITY
│
├─ RECOVERY
├─ RECOVERY-VERITY
│
└─ DATA
   ├─ /var
   └─ /home
      ├─ alice.home
      └─ bob.home
```

Bring-up progression:

```
0.0.1   ESP + ROOT (ext4, read-write)
0.0.2   ESP + SYSTEM-A (EROFS) + DATA
0.0.3   ESP + XBOOTLDR + SYSTEM-A/B + VERITY + RECOVERY stub + DATA
```

DATA shall be an ext4 filesystem mounted at `/data`. Its `var` and `home` directories are bind-mounted onto the standard paths:

```
/data         DATA partition (ext4)
/data/var  →  /var     (bind mount)
/data/home →  /home    (bind mount; systemd-homed images <user>.home)
```

`systemd-repart` shall define and construct disk layouts.

## 16. Updates

The update mechanism shall use `systemd-sysupdate`.

Primary update artifacts:

```
SYSTEM image + verity
UKI (installed to XBOOTLDR)
desktop extension
other release-coupled extensions
```

A/B SYSTEM updates shall support rollback. XBOOTLDR shall retain at least the current and previous UKI.

An installed machine shall follow exactly one channel pointer (§17.3). It updates when that pointer names a newer snapshot than the one installed. Switching to a channel whose pointer names an older snapshot shall never downgrade automatically: downgrade is an explicit rollback or recovery operation.

Promotion shall reuse identical artifacts and never rebuild equivalent source states. The digest of a snapshot shall never change.

## 17. Release Model

Rationale: [release-model.md](release-model.md).

> Upstream version labels do not define release maturity. The complete immutable system image
> is the unit of integration, testing, promotion, rollback and support.

### 17.1 Integration Cycles

An integration cycle:

```
resolve every tracked upstream HEAD (§31) to an exact commit
        ↓
exact source manifest
        ↓
build the whole graph
        ↓
integration tests
        ↓
FAIL → record, logs only          GREEN → snapshot
```

Cycles run on a schedule, manually, or when tracked upstreams change. If no tracked input and no project change has moved, no build happens. "Nightly" is only a possible cadence: no build has special status because of when it ran.

### 17.2 Snapshots

A green integration result is a snapshot: installable and immutable, identified by its UTC resolution time:

```
snapshot-YYYYMMDD.HHMM
```

A snapshot covers every profile, architecture and extension built from that source graph. The snapshot identifier is the image's `IMAGE_VERSION`. Its manifest records:
- every source commit, with the nearest upstream tag where meaningful;
- HEAD conformity and pins (§31);
- build provenance (Layer 0 versions).

A failed integration publishes nothing, and `latest-green` stays where it was. The project shall not automatically substitute an older commit for a broken component and publish the result. That would silently turn `latest-green` into an undocumented mixture of stale components.

### 17.3 Pointers and Promotion

| Name | Meaning |
|---|---|
| `latest-green` | Newest snapshot that passed mandatory integration |
| `edge` | A green snapshot that survived additional automated and physical-hardware testing and a short soak |
| `stable` | A green snapshot with enough field evidence to be recommended broadly |
| `checkpoint` | A snapshot retained permanently |

All of these refer to the same class of immutable snapshot. They differ only in accumulated confidence:

```
latest-green → snapshot 107
edge         → snapshot 103
stable       → snapshot 88
```

Promotion moves a pointer. It never rebuilds, re-resolves or changes a byte. Test evidence promotes a snapshot; time alone does not. A snapshot with a known regression is simply never promoted. Once `edge` and `stable` exist, their gates shall require the full supported profile and architecture matrix.

### 17.4 Publication and Retention

Every green snapshot shall be recorded in git: the integration cycle commits the resolved refs and tags that commit `snapshot-<id>`. That tag, the refs and the snapshot id reproduce the snapshot. A cycle on a working tree with uncommitted changes outside the refs files still integrates, but it does not commit or tag, so tags always match real history.

Snapshot binaries shall be published as immutable releases tagged `snapshot-<id>`, using GitHub Releases as a binary registry, marked as prereleases. Channel pointers are signed metadata (for example `channels.json`), not moving git tags.

Retention:

```
ordinary green snapshots         14–30 days
referenced by any pointer        retained
checkpoints                      forever
```

Checkpoints mark snapshots worth keeping: the first snapshot on a new upstream major version or tag, milestone firsts, known-good demonstration images, and fallbacks before major architecture changes.

### 17.5 Maintained Lines

There shall be no maintained (backport) branches unless real demand appears. A maintained line would get its own identity, for example `2027.02.N` derived from a named snapshot. It shall never be presented as a promoted snapshot, because its bytes differ.

### 17.6 Recovery

The RecoveryOS UKI (§20) is the one deliberately conservative artifact and sits outside this model.

## 18. User Management

Three identity categories shall remain separate.

### 18.1 Root Identity

UID 0 shall remain present as a kernel and service security identity.

Interactive root access shall be disabled.

Normal system policy:

```
root password:
    locked

root graphical login:
    disabled

root console login:
    disabled

SSH root login:
    disabled

su:
    absent

sudo:
    absent by default

interactive root shell:
    unsupported during normal boot
```

### 18.2 System Accounts

Services shall prefer:

```
DynamicUser=
```

Stable system identities shall use:

```
systemd-sysusers
```

Sysexts should avoid introducing fixed system users.

Required fixed identities shall belong to the base release definition.

### 18.3 Human Accounts

Early prototypes shall use a conventional fixed development account.

`systemd-homed` shall be introduced only after base authentication and SELinux integration become stable.

Long-term target:

```
systemd-userdb
systemd-homed
PAM
LUKS-backed home storage where appropriate
```

## 19. Administrative Privileges

Administrative authority shall not be synonymous with unrestricted UID-0 command execution.

Preferred architecture:

```
desktop/admin client
        ↓
D-Bus or Varlink API
        ↓
polkit authorization
        ↓
narrow privileged service
```

Possible administrative actions:

```
system update
network configuration
user management
extension management
machine management
reboot
shutdown
time configuration
firmware update
```

Policy roles may include:

```
org.beamline.update
org.beamline.manage-users
org.beamline.manage-network
org.beamline.manage-machines
org.beamline.manage-extensions
org.beamline.manage-hardware
```

A broad administrator role may aggregate policy permissions without granting an unrestricted root shell.

## 20. Recovery Environment

A separately built RecoveryOS shall provide emergency maintenance: a RecoveryOS UKI on XBOOTLDR together with the RECOVERY and RECOVERY-VERITY partitions (§15).

For now the RecoveryOS is a stub with no further requirements. Later it is expected to be based on Grml, and to move slowly and independently of the snapshot stream. Any coreutils it ships follow §7.2.

Normal boot shall not expose unrestricted root-shell functionality.

## 21. SELinux

SELinux shall form part of the intended security architecture.

The initial policy shall be small and distribution-specific rather than an unrestricted import of a large conventional distribution policy.

Primary protected domains shall eventually include:

```
systemd
udev
journald
network stack
resolved
authentication
D-Bus
polkit
Flatpak
PipeWire
Wayland compositor
sysupdate
sysext
nspawn/machined
desktop session
```

The base policy shall define labels required by extensions.

Extension filesystems shall be labelled during image construction before verity/signing.

### 21.1 SELinux Deployment Stages

Suggested progression:

```
Stage 0
    SELinux disabled during earliest bootstrap

Stage 1
    SELinux compiled and policy installed
    permissive mode

Stage 2
    Virt profile enforcing
    zero unexpected AVCs in automated tests

Stage 3
    Hardware profile permissive with real-hardware testing

Stage 4
    Hardware profile enforcing
```

`systemd-homed` integration shall occur after basic SELinux behavior becomes reliable.

## 22. Security Layers

The security model shall use multiple independent layers.

```
signed boot artifacts
        +
dm-verity
        +
immutable /usr
        +
SELinux
        +
systemd service sandboxing
        +
polkit
        +
minimal host software
        +
disabled interactive root
```

Typical service hardening shall consider:

```
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateDevices=yes
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
CapabilityBoundingSet=
SystemCallFilter=
RestrictNamespaces=
```

Service-specific requirements shall determine final settings.

## 23. Development Host Architecture

Primary local development shall target Apple Silicon macOS.

A Linux ARM64 virtual machine shall provide the BuildStream build environment.

Preferred initial VM options:

```
Lima + Virtualization.framework
```

or:

```
Tart + Virtualization.framework
```

The BuildStream cache, kernel object trees, and filesystem staging areas shall reside on a native Linux filesystem inside the VM.

Large build caches shall not reside on macOS shared filesystems.

## 24. Local QEMU Execution

Two local execution modes shall exist.

### 24.1 Native macOS Mode

Default fast path:

```
macOS
   ↓
QEMU
   ↓
HVF
   ↓
Beamline ARM64
```

Build flow:

```
source
   ↓
Linux builder VM
   ↓
BuildStream
   ↓
Beamline ARM64 image
   ↓
QEMU/HVF on macOS
```

This mode shall not require nested virtualization.

### 24.2 Nested Linux Mode

On supported Apple Silicon hardware:

```
macOS
   ↓
Virtualization.framework
   ↓
Linux builder/runner
   ↓
KVM
   ↓
QEMU
   ↓
Beamline
```

Nested KVM shall provide increased CI parity.

Nested virtualization shall remain optional rather than foundational.

## 25. QEMU Acceleration Abstraction

The test harness shall select acceleration automatically.

Expected behavior:

```
macOS:
    HVF

Linux with /dev/kvm:
    KVM

unsupported environment:
    TCG
```

Possible interface:

```
QEMU_ACCEL=auto
QEMU_ACCEL=hvf
QEMU_ACCEL=kvm
QEMU_ACCEL=tcg
```

Test logic shall remain independent of acceleration technology.

## 26. Local and Hosted CI

CI implementation shall live in repository scripts rather than GitHub Actions YAML.

Preferred structure:

```
ci/
├── bootstrap
├── build
├── build-kernel
├── image
├── boot
├── test-base
├── test-desktop
├── test-sysupdate
├── test-all
└── integrate
```

`./ci/integrate` runs one integration cycle (§17.1): it resolves tracked HEADs, runs the full test sequence, and records a snapshot when green.

Local execution:

```
./ci/test-all
```

Hosted execution:

```
GitHub Actions
    ↓
./ci/bootstrap
./ci/test-all
```

GitHub Actions shall remain an execution backend rather than the canonical definition of build logic.

## 27. Architecture Coverage

AArch64 shall serve as the primary local development architecture.

Expected local cadence:

```
AArch64:
    every build
    every kernel test
    every boot test
    every desktop test
```

Hosted CI shall cover:

```
AArch64
x86-64
```

Local x86-64 emulation on Apple Silicon shall remain optional and primarily diagnostic.

## 28. CI Test Isolation

Every virtual-machine test shall use a clean writable overlay over an immutable base image.

Example:

```
base.raw
   +
temporary qcow2 overlay
        ↓
isolated test VM
```

Parallel tests may include:

```
boot
login
network
desktop
sysext
sysupdate
rollback
SELinux
corruption recovery
```

The original system artifact shall never be modified by testing.

## 29. QEMU Test Protocol

The earliest boot test may use a serial success marker:

```
BEAMLINE_BOOT_OK
```

Later tests shall verify:

```
system health
network connectivity
DNS resolution
journald
extension activation
container execution
Wayland session startup
PipeWire startup
Flatpak functionality
sysupdate
rollback
SELinux state
clean shutdown
```

Virt shall serve as the deepest automated test target.

Hardware images shall still receive basic QEMU boot validation where possible.

## 30. Desktop Testing

The earliest desktop extension may use a directory extension:

```
/var/lib/extensions/desktop/
└── usr/
```

Initial validation:

```
systemd-sysext merge
        ↓
desktop binaries appear under /usr
        ↓
Wayland compositor starts
```

After successful integration, the directory extension shall become an EROFS/raw extension image.

Signed and verity-protected extension delivery shall follow later.

## 31. Upstream Tracking Policy

`policy/tracking.toml` shall define the designated upstream development branch of every tracked component.

```
Freedesktop SDK   master
Linux             master (torvalds)
systemd           main
dash              master

later:
Mesa              main
PipeWire          master
WirePlumber       main
labwc             master
wlroots           master
```

Rule: track the designated branch unless an explicit temporary exception exists. Never guess which branch looks newest.

Components inside Freedesktop SDK that are not tracked individually follow FDSDK master. Closely coupled components need no separate cohort rules, because every integration cycle resolves all HEADs together.

### 31.1 Selection

A component's selected commit is its branch HEAD at resolution time. For Freedesktop SDK, the selected commit is the newest `master` commit whose upstream CI pipeline succeeded, so that FDSDK's published artifacts exist for it. The manifest records any lag behind master HEAD.

### 31.2 Pins

A temporary pin is a visible exception. It shall be recorded in `policy/tracking.toml` with a reason and an issue, and reported in every manifest:

```
mesa:
    tracking: main
    upstream_head: abcdef1
    selected:      1234567
    status: PINNED
    reason: regression
    issue: #493
```

HEAD conformity (for example `7 / 8 at designated HEAD`) is a release metric. Target: no tracked component normally remains behind its designated branch for more than 24 hours.

### 31.3 Layers

```
Layer 0   runner bootstrap        BuildStream, buildbox, builder VM/runner image,
                                  BuildStream plugin junctions            pinned
Layer 1   FDSDK bootstrap         compiler, libc, toolchain               via FDSDK master
Layer 2   Beamline integration graph  FDSDK + tracked overrides + owned       tracked HEADs
Layer 3   snapshot artifacts      SYSTEM images, UKIs, sysexts, manifest
```

Layer 0 is not part of the source graph. It stays pinned to known-good versions, changes deliberately, and is recorded as provenance. A BuildStream regression must never be confused with an upstream integration regression.

### 31.4 Overrides

An element override that tracks a component outside FDSDK's own selection is a copy of an FDSDK recipe. When a tracked FDSDK update changes the original recipe, the integration cycle shall fail until the override is re-copied from the new recipe. Drift is never allowed to accumulate silently.

## 32. Integration Reporting

Integration cycles replace per-component update pull requests.

Each cycle shall report:

```
snapshot id and previous green snapshot
per-component old and new commits, nearest tags
HEAD conformity and pins
new kernel configuration symbols
build result
boot result
integration-test result
```

When a cycle fails, the report shall identify which tracked inputs changed since the last green snapshot. Upstream breakage is then attributed visibly instead of being hidden.

## 33. Build and Artifact Caching

Freedesktop SDK public BuildStream artifacts shall be reused whenever possible.

Local BuildStream caches shall persist inside the Linux development VM.

GitHub cache mechanisms may accelerate hosted jobs but shall not become required for reproducibility.

Loss of a CI cache shall cause slower builds, not broken builds.

## 34. Repository Layout

Structure (entries marked `later` arrive with their milestones):

```
beamline/
├── project.conf
├── project.refs              source pins (written by integration cycles)
├── junction.refs             junction pins
│
├── include/
│   ├── aliases.yml
│   ├── snapshot.yml          snapshot identifier (dev outside integration)
│   └── kernel/               shared kernel source and build rules
│
├── elements/
│   ├── junctions/            freedesktop-sdk.bst, BuildStream plugin junctions
│   ├── base/                 runtime, systemd, ipc, security, shell-compat, os-release, base
│   ├── overrides/            FDSDK element overrides tracked at upstream HEAD (systemd, ...)
│   ├── kernel/               linux-virt.bst, linux-hardware.bst (later), config.bst
│   ├── profiles/             virt.bst, hardware.bst (later)
│   ├── desktop/              later
│   ├── extensions/           desktop/admin/devel sysexts (later)
│   ├── image/                root, initrd, UKI and disk composition per profile
│   └── tests/                tests that run inside BuildStream
│
├── files/                    OS configuration: base, network, kernel, repart, overrides, ...
├── policy/
│   ├── tracking.toml         designated branches, selection, pins
│   └── unit-shell-allowlist.txt
├── ci/                       bootstrap, check, build, build-kernel, image, boot,
│                             test-base, test-all, integrate
├── tools/                    integrate.py, qemu-test.py, check-policy.py, ...
├── lima/                     builder VM definition
├── docs/                     spec.md, release-model.md, decisions.md
└── .github/workflows/        thin hosted orchestration
```

Responsibility separation:

```
elements/
    build graph

files/
    operating-system configuration

policy/
    source tracking and release policy

ci/
    portable build/test/integration workflow

tools/
    integration and maintenance automation

.github/
    hosted runner orchestration
```

## 35. Bootstrap Strategy

Initial development shall use a stable Freedesktop SDK release rather than immediately combining all bleeding-edge inputs. Once the first image boots, inputs move to their tracked upstream HEADs (§31) one at a time.

```
known-good FDSDK release
        ↓
minimal base
        ↓
QEMU boot
        ↓
project-owned Virt kernel
        ↓
UKI
        ↓
inputs to tracked HEADs, one at a time:
FDSDK master → Linux master → systemd main
        ↓
EROFS SYSTEM + DATA
        ↓
desktop sysext
        ↓
verity
        ↓
A/B sysupdate + XBOOTLDR
        ↓
Hardware profile
        ↓
SELinux
        ↓
homed
```

Multiple experimental dimensions shall not be introduced simultaneously during bootstrap. This applies to structural changes to the repository; integration cycles move all tracked HEADs together by design.

## 36. Initial 0.0.1 Scope

Version `0.0.1` shall target only a bootable AArch64 Virt image.

Required components:

```
Freedesktop SDK minimal runtime
systemd
D-Bus broker
dash
kmod
minimal util-linux support
required crypto/filesystem libraries
systemd-networkd
systemd-resolved
Linux Virt kernel
systemd-based initrd
UKI
QEMU virt
UEFI/OVMF
serial console
```

Explicit exclusions:

```
desktop
NetworkManager
hardware image
systemd-homed
SELinux enforcement
Secure Boot
A/B updates
sysupdate
dm-verity if blocking earliest bring-up
physical hardware support
```

Primary success criterion:

A clean source checkout can produce a bootable AArch64 image inside the Linux builder VM, and the resulting image can boot successfully under QEMU/HVF on Apple Silicon.

## 37. 0.0.2 Scope

Expected additions:

```
EROFS SYSTEM-A partition
DATA partition (/var, /home)
desktop directory sysext
labwc graphical session
PipeWire
Wayland
basic Flatpak support
admin sysext (uutils multicall)
automated QEMU desktop test
```

## 38. 0.0.3 Scope

Expected additions:

```
desktop raw/EROFS sysext
dm-verity
A/B SYSTEM layout
XBOOTLDR with current and previous UKIs
RECOVERY partition and RecoveryOS stub UKI
systemd-sysupdate following a channel pointer
rollback tests
signed UKI development keys
```

## 39. 0.1 Scope

Expected additions:

```
Hardware profile
NetworkManager
linux-firmware
broad hardware kernel
x86-64 and ARM64 hosted integration cycles
snapshot publication (GitHub Releases), latest-green pointer, retention
```

## 40. Later Security Milestones

Expected progression:

```
SELinux permissive
        ↓
Virt SELinux enforcing
        ↓
root-login removal
        ↓
polkit-based administration
        ↓
signed recovery UKI
        ↓
systemd-homed
        ↓
Hardware SELinux enforcing
        ↓
Secure Boot production key workflow
        ↓
TPM-bound secrets and measured boot
```

## 41. Non-Goals

Initial development shall not attempt:

* compatibility with arbitrary Linux packages;
* traditional package-manager workflows;
* mutable `/usr`;
* DKMS;
* arbitrary QEMU hardware emulation;
* every desktop environment;
* immediate shell-less operation;
* immediate `systemd-homed` adoption;
* immediate SELinux enforcement on physical hardware;
* independent versioning of every sysext;
* stable/testing/unstable source sets or per-package maturity policy;
* maintained (backport) release branches before real demand exists;
* forking the Freedesktop SDK bootstrap;
* perfect support for all physical devices;
* local x86-64 builds as the main Apple Silicon development path.

## 42. Architectural Invariants

The following rules should remain stable unless strong evidence justifies revision:

1. `/usr` is generated, not administered.
2. Installed-system package managers do not exist.
3. Exact source revisions define releases.
4. BuildStream performs dependency resolution.
5. Freedesktop SDK supplies reusable infrastructure rather than final policy.
6. Systemd provides the primary operating-system framework.
7. Hardware and Virt remain profiles of one distribution.
8. Base operation does not require a desktop.
9. Desktop software remains separable through sysext.
10. Bash remains outside the base.
11. Base systemd services do not depend on shell scripting.
12. UID 0 remains an implementation identity rather than a normal login identity.
13. Administrative authority uses narrow privileged APIs.
14. Recovery uses a separate signed environment.
15. Kernel builds belong to the project.
16. Upstream version labels do not define release maturity; the complete image is the unit of integration, testing, promotion, rollback and support.
17. CI runs locally before hosted execution.
18. GitHub Actions does not contain the canonical build logic.
19. AArch64 remains a first-class architecture.
20. Virt remains the deterministic integration-test platform.
21. Immutable artifacts receive promotion rather than reconstruction.
22. SELinux policy remains part of the release artifact.
23. Extension compatibility remains explicit and release-coupled.
24. Security features add layers rather than replacing existing layers.
25. Minimalism serves architectural clarity rather than minimum byte count.
26. Designated upstream HEADs are tracked; pins are explicit, visible exceptions.
27. A failed integration never publishes, and stale components are never substituted silently.
28. Build tooling (Layer 0) stays pinned and outside the source graph.
29. The initrd is project-owned and built from the image's own tree; dracut is not used.
30. Coreutils shipped in any artifact are uutils, as a single multicall binary.

## 43. Summary Architecture

```
                       UPSTREAM HEADs
   FDSDK master / Linux master / systemd main / Mesa / labwc ...
                            │
                   integration cycle (§17)
                            │
              resolve → manifest → build → test
                            │
                   ┌────────┴────────┐
                 FAIL              GREEN SNAPSHOT
               logs only             │
                                     │  latest-green → edge → stable
                                     ▼  (pointers; no rebuild)
                      BEAMLINE BASE (on FDSDK + overrides)
      ┌──────────────────────────────────────┐
      │ systemd                              │
      │ glibc                                │
      │ D-Bus                                │
      │ PAM / userdb                         │
      │ polkit                               │
      │ journald                             │
      │ sysupdate / sysext / repart          │
      │ minimal /bin/sh (dash)               │
      │ immutable root infrastructure        │
      └──────────────────────────────────────┘
                            │
               ┌────────────┴────────────┐
               │                         │
        HARDWARE PROFILE            VIRT PROFILE
               │                         │
       NetworkManager               networkd
       broad kernel                 narrow kernel
       firmware                     VirtIO ABI
       fwupd                        no firmware
               │                         │
               └────────────┬────────────┘
                            │
          SYSTEM-A / SYSTEM-B (EROFS + dm-verity)
                            │
           signed UKIs on XBOOTLDR, project-owned initrd
                            │
                   systemd-sysupdate
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
 desktop.sysext       admin.sysext        devel.sysext
        │              (uutils)
   labwc / LXQt
   Wayland
   PipeWire
   Flatpak
                            │
                 USER SESSION (DATA: /var, /home)
                            │
                  polkit / SELinux
                            │
                  privileged services
                            │
                       no root login

  Separate, deliberately boring: RecoveryOS UKI + RECOVERY partition
```

The resulting system shall resemble an appliance-oriented operating system internally while retaining the graphical usability and hardware flexibility expected from a modern Linux workstation. Every published system image is an immutable, reproducible snapshot of upstream HEADs that passed end-to-end OS integration testing.
