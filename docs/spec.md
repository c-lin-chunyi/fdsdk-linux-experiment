# Immutable Linux OS Development Specification

- Status: Initial development specification
- Target maturity: Experimental / developer-oriented
- Primary architecture: AArch64 and x86-64
- Primary development host: Apple Silicon macOS
- Primary build system: BuildStream 2
- Primary upstream substrate: Freedesktop SDK
- Primary system framework: systemd

> This file is the project's authoritative specification. Deliberate deviations and
> interpretations are recorded in [decisions.md](decisions.md), not by editing this text.

## 1. Project Objective

The project defines a source-built, image-native Linux operating system designed around a small immutable host, systemd-native lifecycle management, reproducible BuildStream composition, optional system extensions, and strongly separated hardware profiles.

The deployed operating system shall contain no traditional package manager and shall not treat the installed root filesystem as a mutable package environment.

The base system shall function as a verified appliance. Graphical desktop software, administrative utilities, development tools, and other nonessential facilities shall exist outside the smallest bootable base whenever practical.

The architecture shall prioritize:

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
coreutils
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

### 11.2 Kernel Source Channels

Three primary source channels shall exist:

```
release
    latest selected final upstream release

rc
    latest selected vX.Y-rcN tag

main
    daily pinned snapshot of Linus master
```

Optional additional channel:

```
stable-rc
    CI-only testing of pending stable updates
```

`main` and `rc` shall remain distinct.

The `rc` channel shall serve as the more practical pre-release testing lane.

The `main` channel shall serve as the highest-churn upstream-integration lane.

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

The initial Virt kernel shall prioritize successful boot over aggressive size optimization.

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
signed UKI
        ↓
systemd-stub
        ↓
Linux
        ↓
systemd-based initrd
        ↓
dm-verity root discovery
        ↓
immutable root
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

Kernel compilation and UKI generation shall remain separate BuildStream stages.

## 14. Root Filesystem

The final root filesystem shall be read-only and cryptographically verifiable.

Preferred format:

```
EROFS
+
dm-verity
```

Persistent mutable state shall live outside the root image.

Primary writable areas:

```
/var
/home or homed-managed storage
runtime state under /run
```

Arbitrary persistent mutation of `/etc` shall be minimized.

`systemd-confext` may provide declarative configuration overlays.

## 15. Disk Layout

Initial bootstrap layout:

```
GPT
├── ESP
├── ROOT
└── VAR
```

Final update-capable layout:

```
GPT
├── ESP
├── ROOT-A
├── ROOT-B
└── VAR
```

Optional separate home or state partitions may be introduced later.

`systemd-repart` shall define and construct disk layouts.

## 16. Updates

The final update mechanism shall use `systemd-sysupdate`.

Primary update artifacts:

```
root image
UKI
desktop extension
other release-coupled extensions
```

A/B root updates shall support rollback.

Stable promotion shall reuse identical artifacts rather than rebuilding equivalent source states.

Example channel promotion:

```
canary
   ↓
edge
   ↓
stable
```

The digest shall remain unchanged during promotion.

## 17. Release Streams

Suggested release policy:

```
canary-main
    daily selected upstream snapshots
    Linux master
    optionally systemd main
    optionally Mesa main

canary-rc
    latest kernel RC
    newer but less chaotic component set

edge
    latest selected final releases
    short soak period

stable
    promoted known-good artifacts
```

Channel identity shall describe promotion state rather than separate source trees.

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
org.example.update
org.example.manage-users
org.example.manage-network
org.example.manage-machines
org.example.manage-extensions
org.example.manage-hardware
```

A broad administrator role may aggregate policy permissions without granting an unrestricted root shell.

## 20. Recovery Environment

A separately signed recovery UKI shall provide emergency maintenance.

Example ESP contents:

```
MyOS-current.efi
MyOS-previous.efi
MyOS-Recovery.efi
```

The recovery environment may include:

```
bash
coreutils
cryptsetup
filesystem repair tools
systemd-dissect
systemd-repart
systemd-sysupdate
mount tools
network diagnostics
journal tools
```

Normal boot shall not expose equivalent unrestricted root-shell functionality.

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
MyOS ARM64
```

Build flow:

```
source
   ↓
Linux builder VM
   ↓
BuildStream
   ↓
MyOS ARM64 image
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
MyOS
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
└── test-all
```

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
MYOS_BOOT_OK
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

## 31. Component Update Policy

A repository policy file shall describe upstream tracking.

Example:

```
systemd:
    source: upstream Git
    canary: main
    edge: latest final release

Linux:
    canary-main: Linus master
    canary-rc: latest RC
    edge: latest final release

Mesa:
    canary: main
    edge: latest release

PipeWire:
    canary: upstream branch
    edge: release

labwc:
    canary: upstream branch
    edge: known-good revision
```

Closely coupled components shall update as cohorts.

Possible cohorts:

```
graphics:
    Mesa
    libdrm
    Wayland
    wayland-protocols

audio:
    PipeWire
    WirePlumber

compositor:
    wlroots
    labwc
```

## 32. Automated Update Pull Requests

Automated dependency updates shall generate focused pull requests.

Preferred pattern:

```
systemd update → one PR
Linux update   → one PR
graphics stack → one PR
audio stack    → one PR
```

Large unrelated dependency batches shall be avoided.

Each update PR should report:

```
old revision
new revision
upstream version/tag
new kernel configuration symbols where relevant
build result
boot result
integration-test result
```

## 33. Build and Artifact Caching

Freedesktop SDK public BuildStream artifacts shall be reused whenever possible.

Local BuildStream caches shall persist inside the Linux development VM.

GitHub cache mechanisms may accelerate hosted jobs but shall not become required for reproducibility.

Loss of a CI cache shall cause slower builds, not broken builds.

## 34. Repository Layout

Recommended initial structure:

```
myos/
├── project.conf
├── project.refs
├── junction.refs
│
├── elements/
│   ├── junctions/
│   │   └── freedesktop-sdk.bst
│   │
│   ├── base/
│   │   ├── runtime.bst
│   │   ├── systemd.bst
│   │   ├── ipc.bst
│   │   ├── security.bst
│   │   ├── shell-compat.bst
│   │   ├── os-release.bst
│   │   └── base.bst
│   │
│   ├── overrides/
│   │   ├── systemd.bst
│   │   ├── mesa.bst
│   │   └── pipewire.bst
│   │
│   ├── kernel/
│   │   ├── linux-release.bst
│   │   ├── linux-rc.bst
│   │   ├── linux-main.bst
│   │   ├── linux-hardware.bst
│   │   └── linux-virt.bst
│   │
│   ├── profiles/
│   │   ├── hardware.bst
│   │   └── virt.bst
│   │
│   ├── desktop/
│   │   ├── graphics.bst
│   │   ├── wayland.bst
│   │   ├── audio.bst
│   │   ├── flatpak.bst
│   │   ├── labwc.bst
│   │   ├── lxqt.bst
│   │   └── desktop.bst
│   │
│   ├── extensions/
│   │   ├── desktop-tree.bst
│   │   ├── desktop-sysext.bst
│   │   ├── admin-tree.bst
│   │   ├── admin-sysext.bst
│   │   └── devel-sysext.bst
│   │
│   ├── image/
│   │   ├── root-hardware.bst
│   │   ├── root-virt.bst
│   │   ├── initrd.bst
│   │   ├── uki-hardware.bst
│   │   ├── uki-virt.bst
│   │   ├── disk-hardware.bst
│   │   └── disk-virt.bst
│   │
│   └── tests/
│       ├── boot-virt.bst
│       ├── base-health.bst
│       ├── desktop-health.bst
│       └── sysupdate-health.bst
│
├── files/
│   ├── base/
│   │   ├── os-release
│   │   ├── tmpfiles.d/
│   │   ├── sysusers.d/
│   │   └── systemd/
│   │
│   ├── kernel/
│   │   └── config/
│   │       ├── common.config
│   │       ├── hardware.config
│   │       └── virt.config
│   │
│   ├── network/
│   │   ├── networkd/
│   │   └── NetworkManager/
│   │
│   ├── repart/
│   ├── sysupdate/
│   ├── desktop/
│   ├── polkit/
│   └── selinux/
│
├── policy/
│   ├── components.toml
│   └── kernel.toml
│
├── ci/
│   ├── bootstrap
│   ├── build
│   ├── build-kernel
│   ├── image
│   ├── boot
│   ├── test-base
│   ├── test-desktop
│   ├── test-sysupdate
│   └── test-all
│
├── tools/
│   ├── update-component.py
│   ├── update-kernel.py
│   ├── make-sysext.py
│   ├── make-image.py
│   └── qemu-test.py
│
└── .github/
    └── workflows/
        ├── pr.yml
        ├── nightly.yml
        ├── kernel-main.yml
        └── release.yml
```

Responsibility separation:

```
elements/
    build graph

files/
    operating-system configuration

policy/
    source and release policy

ci/
    portable build/test workflow

tools/
    maintenance automation

.github/
    hosted runner orchestration
```

## 35. Bootstrap Strategy

Initial development shall use a stable Freedesktop SDK release rather than immediately combining all bleeding-edge inputs.

Initial sequence:

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
EROFS
        ↓
desktop sysext
        ↓
verity
        ↓
A/B sysupdate
        ↓
Hardware profile
        ↓
newer systemd
        ↓
kernel RC/main
        ↓
SELinux
        ↓
homed
```

Multiple experimental dimensions shall not be introduced simultaneously during bootstrap.

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
EROFS root
desktop directory sysext
labwc graphical session
PipeWire
Wayland
basic Flatpak support
admin sysext
automated QEMU desktop test
```

## 38. 0.0.3 Scope

Expected additions:

```
desktop raw/EROFS sysext
dm-verity
A/B root layout
systemd-sysupdate
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
x86-64 CI
ARM64 CI
kernel release/RC/main lanes
component update automation
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
16. Kernel release, RC, and mainline channels remain distinct.
17. CI runs locally before hosted execution.
18. GitHub Actions does not contain the canonical build logic.
19. AArch64 remains a first-class architecture.
20. Virt remains the deterministic integration-test platform.
21. Immutable artifacts receive promotion rather than reconstruction.
22. SELinux policy remains part of the release artifact.
23. Extension compatibility remains explicit and release-coupled.
24. Security features add layers rather than replacing existing layers.
25. Minimalism serves architectural clarity rather than minimum byte count.

## 43. Summary Architecture

```
                         UPSTREAM
     Linux / systemd / Mesa / PipeWire / labwc / etc.
                            │
                            ▼
                 FREEDESKTOP SDK
                            │
                   BuildStream junction
                            │
              refs / selective overrides
                            │
                            ▼
                      MYOS BASE
      ┌──────────────────────────────────────┐
      │ systemd                              │
      │ glibc                                │
      │ D-Bus                                │
      │ PAM / userdb                         │
      │ polkit                               │
      │ journald                             │
      │ sysupdate / sysext / repart          │
      │ minimal /bin/sh                      │
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
                  EROFS + dm-verity
                            │
                        signed UKI
                            │
                   systemd-sysupdate
                            │
                 A/B immutable deployment
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
 desktop.sysext       admin.sysext        devel.sysext
        │
   labwc / LXQt
   Wayland
   PipeWire
   Flatpak
                            │
                     USER SESSION
                            │
                  polkit / SELinux
                            │
                  privileged services
                            │
                       no root login
```

The resulting system shall resemble an appliance-oriented operating system internally while retaining the graphical usability and hardware flexibility expected from a modern Linux workstation.
