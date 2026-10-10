# Immutable Linux OS Development Specification

- Status: Initial development specification
- Target maturity: Experimental / developer-oriented
- Primary architecture: AArch64 and x86-64
- Primary development host: Apple Silicon macOS
- Primary build system: BuildStream 2
- Primary upstream substrate: Freedesktop SDK
- Desktop recipe source: gnome-build-meta (GNOME)
- Primary system framework: systemd
- Revision: 7 (2026-10-10)

> This file is the project's authoritative specification. The project owner changes it by
> publishing a new revision. Deviations and interpretations made while implementing it are
> recorded in [decisions.md](decisions.md). [security.md](security.md) is a normative annex
> that governs security matters.

## Revision History

- **Revision 7 (2026-10-10).**
  - Extensions compose four experiences: the base alone (healthy, not meaningfully
    interactive), base + desktop, base + `posix` (a traditional UNIX server), and all
    together (§5.1).
  - The base exposes no interpreter a user can run, other than `/bin/sh`: Python leaves it.
    `dash` stays as `/bin/sh` for compatibility (§5.2, §6).
  - Human accounts get no interactive shell by default: their login shell is
    `beamline-shell`, a stub that explains how to get one (§6, §18.3).
  - The administrative and development extensions become `posix` and `posix-devel`. Their
    contents follow POSIX.1-2024 instead of a hand-picked list (§7.2, §7.3). Printing and
    scanning move to `printing-scanning`; Avahi joins the base (§5.2, §7.4).
  - GNOME Shell's extension support is removed. A `desktop-gnome-advanced` alternative may
    restore it later (§7.1).
  - No artifact contains setuid, setgid or file-capability binaries, except `fusermount3`
    until a setuid-free FUSE exists (§22).
  - 0.0.4 scope is added as §39; the sections after it are renumbered (§39–§44).
- **Revision 6 (2026-10-09).**
  - Human accounts are systemd-homed users (LUKS + btrfs) from 0.0.3, created at first boot.
    GDM autologin ends: homed needs the password to activate a home area (§18.3, §30).
  - Root is locked with a nologin shell. run0 is the only escalation path: polkit decides
    who, a confined SELinux admin domain decides what (§18.1, §19).
  - `/etc` stays read-only except an allowlist of system settings, written through a mutable
    confext layer on DATA and scoped by SELinux labels. The machine ID is saved on DATA and
    bound in by the initrd (§14).
  - Extensions are signed, verity-protected images coupled to their snapshot; each
    snapshot's images live side by side on DATA, so a rollback finds its own (§8, §16).
  - The channel pointers are `latest` (formerly `latest-green`) and `edge`. There is no
    `stable` channel (§17.3).
  - sysupdate follows a channel directory with a signed SHA256SUMS; `gpg` joins the base for
    that, and polkit is part of the base (§5.2, §7.1, §16).
  - Every extension depends only on the base image; extensions never depend on each other
    and are never layered. Variants are mutually exclusive alternatives (§8).
  - 0.0.3 scope and the security progression are updated (§38, §40, §41, §42).
- **Revision 5 (2026-10-08).**
  - The Linux source is GitHub's archive of the selected `master` commit, an explicit
    trade-off against fetching `linux.git` (§11.2).
  - The desktop is GNOME, shipped as the `desktop-gnome` extension. Terminals and other
    desktop utilities come from Flatpak. labwc, wlroots, Qt and LXQt leave the plan (§7.1, §9).
  - GNOME is built from gnome-build-meta's recipes, used as a recipe source only. Beamline
    keeps its own selections of FDSDK, systemd and Linux, and builds GNOME locally (§2.2, §31).
  - No web engine or web JavaScript engine (WebKitGTK, JavaScriptCoreGTK, Chromium/CEF)
    enters any final artifact (§7.1, §42).
  - The SYSTEM image, `/etc` included, is read-only. Users are created at build time, and the
    prototype account is defined at boot by a credential (§14, §18).
  - Extensions are EROFS images from the start, each paired with a confext for its `/etc`
    content. There is no directory-extension stage (§8, §30).
  - DATA grows to fill the disk at first boot (§15). 0.0.2 and 0.0.3 scope are updated
    (§37, §38).
- **Revision 4 (2026-10-08).**
  - Security architecture: a mandatory integrity hierarchy (Biba-style P0–P3) on SELinux,
    defined in the normative annex [security.md](security.md). §18–§22 now summarise it.
  - The SELinux policy is written from scratch in CIL, with MCS from the start (§21).
  - Security stages are tied to milestones: Stage 0 (permissive, labelled images) with 0.0.2,
    and Stage 1 (Virt enforcing) with 0.0.3 (§21, §37, §38, §40).
  - Development keys are committed to the repository. Every snapshot ships a permissive
    development UKI, signed only with the development key (§13, §16).
  - Integrity invariants are added (§42). The Server profile and self-hosted builds are
    deferred (§41).
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

Other upstream BuildStream projects are used the same way: as recipe sources, not as integration authorities. The GNOME desktop (§9) is built from gnome-build-meta's recipes, selected at its `master`. Beamline does not adopt another project's selections for FDSDK, systemd or the kernel. gnome-build-meta's GNOME components are built against Beamline's own FDSDK master. The SDK-library overrides that gnome-build-meta applies to FDSDK (GLib, GTK, Pango and others) are carried in Beamline's FDSDK junction, under the drift rule of §31.4. This independence has a price: GNOME artifacts cannot come from gnome-build-meta's caches and are built locally.

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

The base alone is a healthy system, but not a meaningfully interactive one. Extensions compose
the experiences above it:

```
base                         healthy; no interactive environment
base + desktop-gnome         a conventional desktop, without an interactive UNIX environment
base + posix                 a traditional interactive UNIX server
base + desktop-gnome + posix both
```

The base exposes no interpreter that a user can run, other than `/bin/sh` (§6): no Python,
Perl, Lua or JavaScript runtime. Interpreters embedded in a component that only run system code
(polkit's rules engine, for one) are not exposed and may remain. Lower-integrity code stays
possible (security §10.1), but uncomfortable: Flatpak applications and binaries a user brings to
their own home are allowed; the base just does not hand out interpreters.

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
homed
userdbd
machined
nspawn

D-Bus broker
polkit core (without pkexec)
PAM
NSS/userdb

kmod
cryptsetup libraries/tools required by boot and homed
verity tooling
mkfs.btrfs (homed home areas)
gpg (update signature verification only)
util-linux and other tools only where a base service needs them
Avahi (mDNS/DNS-SD; systemd-resolved's multicast DNS stays off)

CA certificates
crypto libraries

dash as /bin/sh (the only interpreter a user can run, §6)
beamline-shell (the default login shell, a stub, §6)

libselinux
SELinux policy (CIL, MCS) and file contexts
```

Additional libraries shall enter the base only through demonstrated runtime requirements.

The base systemd build shall leave out features the base does not use: journal-remote and journal-upload, QR-code output, xkbcommon keymap validation, and AppArmor (SELinux is the planned security module, §21). Features that later milestones need stay enabled: TPM2, FIDO2, cryptsetup, and curl for `systemd-sysupdate` downloads.

## 6. Shell and Command-Line Policy

Bash shall not be part of the base image. `/usr/bin/bash` comes with the `posix` extension
(§7.2).

A small POSIX-compatible `/bin/sh` shall remain available as a compatibility interface. Base
components and extensions run it non-interactively: Xwayland's session scripts, Flatpak's
triggers, CUPS filters, build tools.

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

Human accounts get no interactive shell by default. Their login shell is
`/usr/libexec/beamline-shell`, listed in `/etc/shells` and built into systemd-homed as the
default shell:

```
run interactively     prints how to get a shell (an administrator enables posix;
                      homectl update --shell=/usr/bin/bash; a Flatpak terminal's command)
                      and exits
run as an interpreter fails with a non-zero status
(-c, a script, no terminal)
```

A user may make `/usr/bin/bash` their shell once `posix` is enabled. Root's shell stays nologin
(§18.1). The initrd contains no shell.

## 7. System Extensions

The official system extensions:

```
desktop-gnome        the GNOME desktop                                    (§7.1)
posix                POSIX userspace and system tools, bash                (§7.2)
posix-devel          POSIX development utilities and toolchains            (§7.3)
printing-scanning    CUPS, SANE and drivers                                (§7.4)
```

Later alternatives, each a complete extension that excludes the one it varies (§8):
`desktop-gnome-advanced` (GNOME with more user customization, Shell extensions included) and a
KDE desktop.

Where an external specification defines what a class of tools must provide, the extension
follows the specification instead of a hand-picked list.

### 7.1 Desktop Extension

`desktop-gnome` shall contain the GNOME desktop and its graphical runtime: a system extension for `/usr`, paired with a configuration extension for `/etc`.

Contents:

```
GNOME Shell and Mutter (Wayland)
GDM
GNOME Session and GNOME Settings Daemon
GNOME Settings (gnome-control-center)
Nautilus
File Roller
GNOME Software (Flatpak backend)
GVfs, dconf, accountsservice, upower
xdg-desktop-portal with the GNOME and GTK backends
PipeWire and WirePlumber
Mesa
Flatpak
GNOME Shell as the graphical polkit agent (polkit itself is base, §5.2)
libcups, for GTK's print dialog (the printing services are §7.4)
fonts, icons, backgrounds, schemas
```

GNOME Shell's extension support is removed when it is built: extensions run user-provided
JavaScript inside the shell. The interpreters that only serve the desktop internally (GNOME
Shell's SpiderMonkey, WirePlumber's Lua) stay embedded; their user-runnable front ends (`gjs`,
`lua`, `wpexec`) are left out wherever the desktop works without them. Components GNOME pulls in
but the desktop does not need (an SSH server, LVM, firewall and dial-up tools, plymouth,
NetworkManager's command line) are left out where its dependencies allow.

Terminal emulators and other desktop utilities (editors, viewers, browsers, mail, help) shall be delivered as Flatpak applications, not as extension content.

No final artifact (SYSTEM, initrd, UKI or any official extension) shall contain a web engine or a web JavaScript engine: WebKitGTK, JavaScriptCoreGTK, Chromium or CEF. A JIT engine executing remote content is lower-integrity dynamic code ([security.md](security.md) §8.2). Web content runs inside Flatpak applications. Components with an optional web view are built without it; GNOME Online Accounts signs in through the default browser.

Final placement of Mesa, PipeWire and Flatpak between base and desktop extension shall remain subject to integration testing.

### 7.2 POSIX Userspace Extension

`posix` provides the interactive environment the base leaves out. It replaces the earlier
administrative extension.

Its utilities follow POSIX.1-2024 (SUSv5, Issue 8):

```
included    the mandatory utilities, and the User Portability option
            (vi, man, more, job control, ...)
excluded    XSI-only utilities, SCCS, UUCP, and utilities that need a daemon or
            privilege: at, batch, crontab, mailx, talk, write, mesg, newgrp
elsewhere   lp (printing-scanning, §7.4); development utilities (posix-devel, §7.3)
```

The goal is not a certified UNIX: it is a userspace whose contents an external specification
defines. Each utility uses, in order of preference, uutils (coreutils, and its sibling projects
once they pass their own test suites), GNU, or another implementation. A list of the required
utilities is part of the repository, and the build checks the extension against it.

It also carries:

```
bash (/usr/bin/bash)
mandoc and the POSIX manual pages
named system tools POSIX does not define: filesystem and disk tools, kmod,
    SELinux and audit tools, iproute2, pciutils, usbutils, strace, curl, jq,
    less, file, ...
user-facing tools no base service needs (moved from the base)
```

Normal installations shall not require permanent activation of `posix`.

Coreutils shipped in any Beamline artifact (this extension, the recovery environment, or any later image content) shall be uutils coreutils. It shall be deployed as a single multicall `coreutils` binary, with one symlink per utility. GNU coreutils may still serve as a build-time tool inside BuildStream sandboxes, as long as it never reaches an artifact.

### 7.3 POSIX Development Extension

`posix-devel` shall support software and operating-system development and low-level debugging.
It provides the POSIX C-language and software development utilities (`c17`, `make`, `lex`,
`yacc`, `ar`, `nm`, `strip`, ...) and toolchains.

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

Application development shall preferentially occur inside an `nspawn` development machine rather than directly through `posix-devel`. Rootless containers, when they arrive, map user IDs through a privileged service, not setuid helpers (§22).

### 7.4 Imaging and Printing Extension

`printing-scanning` provides printing and scanning services: the CUPS scheduler, filters and
backends, `lp`, SANE, and printer drivers such as HPLIP. Without it, the desktop still shows
GTK's print dialog (through `libcups`) but has no local printing service. CUPS keeps its state
and configuration on DATA. Printer discovery uses the base's Avahi.

## 8. Extension Compatibility

Extensions shall be release-coupled rather than treated as arbitrary packages.

Every extension depends only on the base image of its snapshot, never on another extension. There is no dependency graph between extensions and no layering: an extension that varies another (for example a `desktop-gnome-advanced` beside `desktop-gnome`) is a separate, complete extension, and the two are mutually exclusive alternatives.

Example:

```
base-42
desktop-gnome-42.raw
posix-42.raw
posix-devel-42.raw
printing-scanning-42.raw
```

Extensions are EROFS images, labelled when they are built ([security.md](security.md) §19.1). From 0.0.3 each is a disk image with a dm-verity hash tree and a signature over its root hash, made with the development key until production keys exist; systemd activates only signed images. An extension's `/etc` content ships as a configuration extension (confext) of the same name. Fixed system users an official extension needs are created in the SYSTEM image when it is built (§18.2).

Extension images live on DATA: systemd refuses extensions stored below `/usr`, the hierarchy they extend. Each snapshot's images are kept under their own names, next to the previous snapshot's:

```
/var/lib/beamline/extensions/desktop-gnome_<snapshot>.raw
/var/lib/beamline/confexts/desktop-gnome_<snapshot>.raw
```

At boot, the running SYSTEM links the images of its own snapshot (`IMAGE_VERSION`) into `/run/extensions` and `/run/confexts`. After a rollback, the older SYSTEM therefore finds its own extensions. On-demand extensions (`posix`, `posix-devel`, `printing-scanning`) are linked the same way when activated.

Only administrators enable or disable extensions. In 0.0.4 an administrator activates an
on-demand extension for the running boot. Persistent choices arrive later with a Beamline
daemon and its `beamlinectl` command, which keep them on DATA. Their rule is that the system
never ends up without an interactive environment by accident: the graphical settings do not
offer to disable the desktop, and `beamlinectl` disables it only while `posix` is enabled.

Compatibility metadata shall use:

```
ID=
SYSEXT_LEVEL=     the snapshot identifier (CONFEXT_LEVEL for confexts)
ARCHITECTURE=
```

The level is the snapshot identifier, in both os-release and extension-release, so an extension merges only into the SYSTEM built with it.

BuildStream shall resolve dependencies before extension generation.

The deployed system shall not perform dependency solving.

Desktop extension updates shall normally activate after reboot rather than through live replacement during an active graphical session.

## 9. Desktop Environment

The graphical environment is GNOME. It is built from gnome-build-meta's recipes (§2.2) and follows GNOME's development branches through gnome-build-meta `master`.

```
GNOME Shell / Mutter (Wayland)
GDM
GNOME core services and Settings
Nautilus, File Roller, GNOME Software
PipeWire / WirePlumber
xdg-desktop-portal
Flatpak (applications, terminals, utilities)
```

The extension takes only what the session needs. GNOME core applications other than Nautilus, File Roller, Settings and Software come from Flatpak.

The graphical environment shall remain replaceable at the extension level: another desktop would be another `desktop-<name>` extension.

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

The commit is resolved against git.kernel.org. Its tree is downloaded as GitHub's archive of that exact commit (`github.com/torvalds/linux/archive/<commit>.tar.gz`) and pinned by the archive's sha256. This is an explicit trade-off: a git fetch of `linux.git` is slow and needs a multi-gigabyte mirror that hosted runners do not keep. It relies on GitHub serving byte-stable archives, which is current practice, not a guarantee. If an archive ever changes, the source can be reconstructed from the commit recorded in the manifest.

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

The Virt kernel shall be narrow. It is configured from `allnoconfig` plus explicit, human-maintained fragments (common, architecture, Virt), rather than from an architecture defconfig, so everything it contains is there on purpose. The boot path and the virtual hardware contract (§4) are built in. Loadable module support remains for optional features. Security features (SELinux, audit, Landlock, IPE, module signing) are explicit fragment entries too ([security.md](security.md) §19.3).

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

The UKI's signed command line carries the SYSTEM image's dm-verity root hash (`roothash=`). The initrd finds SYSTEM and its verity partition by the partition UUIDs derived from that hash, so each UKI boots exactly the SYSTEM image built with it.

Every snapshot shall also ship a development UKI: the same kernel and initrd with SELinux permissive (`enforcing=0`) in its signed command line, signed only with the development key, which production Secure Boot trust excludes ([security.md](security.md) §19.4).

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

`/etc` is part of the SYSTEM image and is read-only. Everything in it is decided when the image is built, except a short allowlist of system settings:

```
system users and groups    created by systemd-sysusers at image build
human accounts             systemd-homed (§18.3); never /etc/passwd or /etc/shadow
profile configuration      the SYSTEM image, or the confext of an extension
system settings            the mutable layer (below), machine-id included
```

The mutable layer: `systemd-confext` runs in mutable mode, with its writable layer on DATA (`/var/lib/extensions.mutable/etc`). The initrd merges it into the root's `/etc` before switch-root (`systemd-confext-sysroot.service`), so systemd starts with the final `/etc`. Only these files may live in it:

```
/etc/hostname, /etc/machine-info        systemd-hostnamed
/etc/localtime, /etc/adjtime            systemd-timedated
/etc/locale.conf, /etc/vconsole.conf    systemd-localed
/etc/machine-id                         systemd-machine-id-commit (first boot)
```

The allowlist is enforced twice:

- **At every merge.** DATA is not verity-protected, so before merging, the initrd rebuilds the layer from the allowlisted files alone. Anything else in it, whether put there by an offline edit of the disk or written during a permissive development boot, is gone at the next boot.
- **At runtime, by SELinux.** Only allowlisted paths carry writable types; no domain, root and platform services included, may create, change, rename or remove any other `/etc` file. This holds wherever SELinux enforces: every production UKI from Stage 1 (§21.1).

The allowlisted files remain unauthenticated input, which the platform services that read them parse ([security.md](security.md) §9.2). Authenticating DATA itself is a Stage 4 evaluation.

Services keep their state under `/var`. Other configuration that must change on a running system arrives through a confext or a new snapshot, never through in-place edits.

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

SYSTEM-A and SYSTEM-B are slot roles. Their GPT labels follow `systemd-sysupdate`: `beamline_<snapshot>` for an installed slot, `_empty` for a free one. RECOVERY and RECOVERY-VERITY are reserved and empty while the RecoveryOS is a stub (§20).

DATA shall be an ext4 filesystem mounted at `/data`. Its `var` and `home` directories are bind-mounted onto the standard paths:

```
/data         DATA partition (ext4)
/data/var  →  /var     (bind mount)
/data/home →  /home    (bind mount; systemd-homed images <user>.home)
```

The image ships DATA at a small fixed size. At first boot, `systemd-repart` grows the partition to the end of the disk, and `systemd-growfs` grows the filesystem. Extension images are delivered on DATA (§8).

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

A channel is published as a directory: its `SHA256SUMS` lists the artifacts of the snapshot it names, and `SHA256SUMS.gpg` signs that list. `systemd-sysupdate` verifies the signature with `gpg` against the Beamline keyring shipped in SYSTEM, which is the committed development key until production keys exist. Promotion rewrites a channel directory; it never rebuilds.

A new UKI is installed with boot counting. A boot is good when `boot-complete.target` is reached. After three failed attempts, systemd-boot falls back to the previous UKI, and the previous SYSTEM finds its own extensions (§8).

An installed machine shall follow exactly one channel pointer (§17.3). Until publication (§40), that channel is fixed by the image (`latest`). It updates when that pointer names a newer snapshot than the one installed. Switching to a channel whose pointer names an older snapshot shall never downgrade automatically: downgrade is an explicit rollback or recovery operation.

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

A failed integration publishes nothing, and `latest` stays where it was. The project shall not automatically substitute an older commit for a broken component and publish the result. That would silently turn `latest` into an undocumented mixture of stale components.

### 17.3 Pointers and Promotion

| Name | Meaning |
|---|---|
| `latest` | Newest snapshot that passed mandatory integration |
| `edge` | A green snapshot that survived additional automated and physical-hardware testing and a short soak |
| `checkpoint` | A snapshot retained permanently |

All of these refer to the same class of immutable snapshot. They differ only in accumulated confidence:

```
latest → snapshot 107
edge   → snapshot 103
```

There is no `stable` channel. Confidence is expressed by `edge` and by checkpoints, not by a slower lane.

Promotion moves a pointer. It never rebuilds, re-resolves or changes a byte. Test evidence promotes a snapshot; time alone does not. A snapshot with a known regression is simply never promoted. Once `edge` exists, its gate shall require the full supported profile and architecture matrix.

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

sudo, pkexec, doas:
    absent

root shell:
    /usr/bin/nologin (root is created with an invalid password and a nologin
    shell at image build)

interactive root shell:
    unsupported during normal boot

privilege escalation:
    run0 only (§19)
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

Human accounts are `systemd-homed` users (from 0.0.3). Each home area is a LUKS2 image on DATA (`/home/<user>.home`) holding a btrfs filesystem, unlocked by the user's password at login. Accounts are created at first boot from `home.create.<user>` credentials, or later through `homectl` under polkit. They never appear in `/etc/passwd` or `/etc/shadow`, which stay part of the read-only SYSTEM image.

homed needs the password to activate a home area, so there is no automatic graphical login.

A new account's shell is `beamline-shell` (§6). A user may switch to `/usr/bin/bash` with
`homectl update --shell=` once `posix` is enabled.

The development and test accounts are defined by the test tooling's credentials. Neither the accounts nor their passwords are baked into the image.

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

Interactive escalation uses `run0` and nothing else. su, sudo, pkexec and doas are never shipped.

```
who     polkit: members of wheel authenticate with their own password
        (auth_admin_keep); everyone else is refused without a prompt
what    SELinux: run0 sessions run in a confined admin domain
```

polkit sees only the transient unit run0 starts, never the command, so it cannot scope what runs. The admin domain does: it cannot change the SELinux mode or policy, load kernel modules, write SYSTEM or a non-allowlisted `/etc` file (§14), or execute files from DATA or home directories. Root's account shell is nologin, which closes console and other logins. `run0` without a command starts the caller's own shell as root, in the same admin domain: an administrator's root shell is always a confined one.

polkit rules are part of SYSTEM (`/usr/share/polkit-1/rules.d`); `/etc/polkit-1/rules.d` stays empty.

run0 is a client of PID 1's transient-unit interface, and so is `systemd-run`; only run0's PAM session leads to the admin domain. A downstream systemd patch (0.0.4, offered upstream afterwards) bounds the transient units a session requests: they run no higher than the caller unless PAM assigns their context, and a requested SELinux context needs the policy's permission to enter it.

SELinux constrains privileged endpoints independently of polkit decisions; request handling rules for privileged services are in [security.md](security.md) §9.

## 20. Recovery Environment

A separately built RecoveryOS shall provide emergency maintenance: a RecoveryOS UKI on XBOOTLDR together with the RECOVERY and RECOVERY-VERITY partitions (§15).

For now the RecoveryOS is a stub with no further requirements: a UKI on XBOOTLDR, built from the Beamline kernel and initrd, that reports itself and powers off, plus the reserved, empty RECOVERY partitions. Later it is expected to be based on Grml, and to move slowly and independently of the snapshot stream. Any coreutils it ships follow §7.2.

Normal boot shall not expose unrestricted root-shell functionality. When the RecoveryOS becomes real, [security.md](security.md) §14.3 governs its authority.

## 21. SELinux and Mandatory Integrity

SELinux is the mandatory access-control foundation of a mandatory integrity architecture, specified in the normative annex [security.md](security.md). In summary:

- Code carries an integrity level from authenticated provenance and explicit endorsement: P3 platform, P2 delegated, P1 restricted application, and P0 arbitrary user code. Execution requires `P(E) ≤ P(C)`: an environment only runs code of equal or higher integrity, and running higher-integrity code never elevates the caller.
- Compilation, interpretation, copying or installation never raises provenance. Endorsement is an explicit, signed decision; signatures are evidence, not authority.
- Ordinary users may run arbitrary P0 software under confined authority. Privileged services never execute mutable code from DATA, user-controlled libraries, or dynamic code.
- The policy is small and distribution-specific, written from scratch in CIL and compiled with `secilc`, with MCS (one sensitivity plus categories) from the start. Type Enforcement implements the integrity domains first; MLS-based integrity ordering is a later evaluation.
- The base policy defines the labels extensions need. Images are labelled when their filesystems are created, from `file_contexts`; BuildStream cannot carry labels.

### 21.1 Deployment Stages

```
Stage 0   with 0.0.2   SELinux built in kernel and userspace, CIL policy with MCS,
                       labelled EROFS images, Virt permissive, AVCs recorded
Stage 1   with 0.0.3   Virt production UKI enforcing, negative tests, zero unexpected
                       AVCs required for green, permissive development UKI per snapshot
Stage 2   after 0.1    Hardware enforcing, confined services and containers
Stage 3   later        privileged execution hardening, production keys, IPE/IMA evaluation
Stage 4   later        MLS integrity evaluation, fs-verity, isolated VMs, attestation
```

`systemd-homed` arrives with 0.0.3, before Stage 1 enforcement, so the enforcing policy covers it.

## 22. Security Layers

The security model shall use multiple independent layers.

```
signed boot artifacts
        +
dm-verity
        +
immutable /usr
        +
SELinux (mandatory integrity hierarchy, security.md)
        +
systemd service sandboxing
        +
polkit
        +
minimal host software
        +
no setuid, setgid or file-capability binaries
        +
disabled interactive root
```

No artifact contains a setuid or setgid binary, or one with file capabilities. Privilege comes
from services that check their callers (polkit, SELinux), not from a binary's mode. The one
exception is `fusermount3`, until a setuid-free way to mount FUSE filesystems exists upstream;
it runs in its own confined SELinux domain. Functions that traditionally need a setuid helper
either leave (`newgrp`, `passwd`, `chsh`) or move to a privileged service (user-ID mapping for
rootless containers).

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

`./ci/integrate` runs one integration cycle (§17.1): it resolves tracked HEADs, runs the full test sequence, and records a snapshot when green. `./ci/test-desktop` boots the image with a virtual GPU and checks the GNOME session (§30).

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

Extensions are EROFS images from the start (§8). There is no directory-extension stage: systemd refuses extensions stored under `/usr`, and a directory tree on DATA cannot carry build-time SELinux labels.

Initial validation:

```
systemd-sysext and systemd-confext merge desktop-gnome
        ↓
GDM starts; the test signs the development account in through the greeter
        ↓
GNOME Shell (Wayland), PipeWire, WirePlumber and the portal run
        ↓
the Flatpak sandbox starts
        ↓
a screen capture is not blank
```

The base shall still boot healthy with every extension masked (§5.1).

Automated tests use a 2D virtio-gpu with software rendering. Accelerated virgl rendering is available for interactive sessions with a QEMU built with virglrenderer.

From 0.0.3 the extensions are signed and verity-protected (§8).

## 31. Upstream Tracking Policy

`policy/tracking.toml` shall define the designated upstream development branch of every tracked component.

```
Freedesktop SDK    master
Linux              master (torvalds; GitHub archive of the commit, §11.2)
systemd            main
dash               master
gnome-build-meta   master (GNOME recipes; GNOME components at its refs)
uutils coreutils   main
SELinux userspace  main (build-time policy tools)
File Roller        master

later:
Mesa               main
PipeWire           master
WirePlumber        main
```

Rule: track the designated branch unless an explicit temporary exception exists. Never guess which branch looks newest.

Components inside Freedesktop SDK that are not tracked individually follow FDSDK master. Closely coupled components need no separate cohort rules, because every integration cycle resolves all HEADs together.

### 31.1 Selection

A component's selected commit is its branch HEAD at resolution time. For Freedesktop SDK, the selected commit is the newest `master` commit whose upstream CI pipeline succeeded, so that FDSDK's published artifacts exist for it. gnome-build-meta is selected the same way, so its recipes are known to build, even though Beamline builds them against its own FDSDK. The manifest records any lag behind master HEAD.

GNOME components follow the refs of the selected gnome-build-meta commit, which tracks GNOME's development branches.

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
Layer 2   Beamline integration graph  FDSDK + gnome-build-meta recipes +      tracked HEADs
                                  tracked overrides + owned
Layer 3   snapshot artifacts      SYSTEM images, UKIs, sysexts, manifest
```

Layer 0 is not part of the source graph. It stays pinned to known-good versions, changes deliberately, and is recorded as provenance. A BuildStream regression must never be confused with an upstream integration regression.

### 31.4 Overrides

An element override that tracks a component outside FDSDK's own selection is a copy of an FDSDK recipe. When a tracked FDSDK update changes the original recipe, the integration cycle shall fail until the override is re-copied from the new recipe. Drift is never allowed to accumulate silently.

The same rule covers overrides of gnome-build-meta recipes, and the SDK-library overrides carried from gnome-build-meta into Beamline's FDSDK junction (§2.2). When gnome-build-meta changes that list, the cycle fails until the junction matches it again.

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

Freedesktop SDK public BuildStream artifacts shall be reused whenever possible. GNOME components are built locally, because they are built against Beamline's FDSDK selection (§2.2).

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
│   ├── junctions/            freedesktop-sdk.bst, gnome-build-meta.bst, plugin junctions
│   ├── base/                 runtime, systemd, ipc, security, shell-compat, os-release, base
│   ├── overrides/            FDSDK and gnome-build-meta element overrides
│   ├── kernel/               linux-virt.bst, linux-hardware.bst (later), config.bst
│   ├── profiles/             virt.bst, hardware.bst (later)
│   ├── security/             SELinux policy and build-only policy tools
│   ├── posix/                posix extension content (uutils, bash, ...)
│   ├── desktop/              desktop-gnome content (project-owned desktop elements)
│   ├── extensions/           sysext and confext images (desktop-gnome, posix, posix-devel,
│   │                         printing-scanning)
│   ├── image/                root, initrd, UKI and disk composition per profile
│   └── tests/                tests that run inside BuildStream
│
├── files/                    OS configuration: base, network, kernel, repart, overrides,
│                             selinux (CIL policy, from Stage 0), keys/dev (development keys,
│                             from 0.0.3), ...
├── policy/
│   ├── tracking.toml         designated branches, selection, pins
│   └── unit-shell-allowlist.txt
├── ci/                       bootstrap, check, build, build-kernel, image, boot,
│                             test-base, test-reboot, test-verity, test-boot-entries,
│                             test-update, test-run0, test-settings, test-security,
│                             test-extensions, test-desktop, test-all, integrate
├── tools/                    integrate.py, qemu-test.py, check-policy.py, ...
├── lima/                     builder VM definition
├── docs/                     spec.md, security.md (normative annex), release-model.md,
│                             decisions.md
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
EROFS SYSTEM + DATA, SELinux Stage 0 (permissive, labelled images)
        ↓
admin and desktop-gnome extensions (EROFS)
        ↓
verity, signed UKIs, SELinux Stage 1 (Virt enforcing)
        ↓
A/B sysupdate + XBOOTLDR
        ↓
Hardware profile
        ↓
SELinux Stage 2 (Hardware enforcing)
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
EROFS SYSTEM-A partition; read-only root, /etc included
DATA partition (/data; /var and /home bind mounts), grown at first boot
SELinux Stage 0 (security.md §16): SELinux in kernel and userspace,
    CIL policy with MCS, labelled EROFS images, Virt permissive,
    AVC denials recorded in integration manifests
extension pipeline: EROFS sysext and confext images, labelled when built
admin sysext (uutils multicall), activated on demand
desktop-gnome: GNOME Shell, GDM, Settings, Nautilus, File Roller,
    GNOME Software, PipeWire, portals, Flatpak
automated QEMU desktop test
```

They are implemented in this order, one structural change per green integration cycle.

## 38. 0.0.3 Scope

Expected additions:

```
stable machine ID, saved on DATA
development keys (committed, development-only): UKIs, extensions,
    updates, kernel modules
dm-verity SYSTEM, root hash in the signed UKI
A/B SYSTEM layout, XBOOTLDR with current and previous UKIs,
    boot counting, RECOVERY partitions and RecoveryOS stub UKI
signed, verity-protected extension images, coupled to their snapshot
systemd-sysupdate following a signed channel directory,
    upgrade and rollback tests
systemd-homed human accounts (LUKS + btrfs)
locked root with a nologin shell; run0 under polkit as the only escalation
scoped mutable /etc (system settings, scoped by SELinux)
SELinux Stage 1 (security.md §16): Virt production UKI enforcing,
    permissive development UKI per snapshot, mandatory negative
    security tests, zero unexpected AVCs required for green,
    module signing with the development key
```

They are implemented in this order, one structural change per green integration cycle. SELinux Stage 1 comes last, so the enforcing policy covers everything before it.

## 39. 0.0.4 Scope

Expected additions:

```
no user-runnable interpreter in the base other than /bin/sh (Python leaves)
beamline-shell as the default login shell
posix replaces the administrative extension; utilities follow POSIX.1-2024;
    user-facing tools leave the base for it
printing-scanning: CUPS, SANE and drivers leave the desktop; Avahi joins the base
desktop-gnome without GNOME Shell extension support or user-runnable interpreters,
    and without components it does not need
no setuid, setgid or file-capability binaries, except fusermount3
posix-devel replaces the development extension
the downstream systemd patch bounding transient units a session requests
```

They are implemented in this order, one structural change per green integration cycle, and a
HEAD integration closes the milestone.

## 40. 0.1 Scope

Expected additions:

```
Hardware profile
NetworkManager
linux-firmware
broad hardware kernel
x86-64 and ARM64 hosted integration cycles
snapshot publication (GitHub Releases), signed latest pointer, retention
```

## 41. Later Security Milestones

Expected progression (stages from [security.md](security.md) §16):

```
Stage 0: SELinux permissive, labelled images          (with 0.0.2)
        ↓
root-login removal, run0 under polkit, systemd-homed  (with 0.0.3)
        ↓
Stage 1: Virt enforcing, development UKI              (with 0.0.3)
        ↓
narrow administration APIs (org.beamline.*)
        ↓
Stage 2: Hardware enforcing                           (after 0.1)
        ↓
Stage 3: production keys, module endorsement, IPE/IMA evaluation
        ↓
Secure Boot production key workflow
        ↓
Stage 4: MLS integrity, TPM-bound secrets and measured boot, attestation
```

## 42. Non-Goals

Initial development shall not attempt:

* compatibility with arbitrary Linux packages;
* traditional package-manager workflows;
* mutable `/usr`;
* DKMS;
* arbitrary QEMU hardware emulation;
* every desktop environment;
* a base without `/bin/sh` (dash stays as a compatibility interface, §6);
* immediate SELinux enforcement on physical hardware;
* independent versioning of every sysext;
* stable/testing/unstable source sets or per-package maturity policy;
* maintained (backport) release branches before real demand exists;
* forking the Freedesktop SDK bootstrap;
* a Server profile, self-hosted construction of successor snapshots, or a generational builder chain (deferred, expected around version 3; [security.md](security.md) §20);
* perfect support for all physical devices;
* local x86-64 builds as the main Apple Silicon development path.

## 43. Architectural Invariants

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
31. Lower-integrity code never executes with higher-integrity authority; running trusted code never elevates its caller ([security.md](security.md) §2).
32. Compilation, interpretation and installation never raise code provenance; endorsement is explicit.
33. Cryptographic verification is evidence, not policy authority.
34. Privileged services never execute mutable code.
35. Ordinary users remain free to execute arbitrary software under confined authority.
36. Integrity is separate from confidentiality and resource-access authority.
37. SELinux enforcement mode belongs to the boot entry, not the release channel; production UKIs of an enforcing profile always enforce.
38. No web engine or web JavaScript engine (WebKitGTK, JavaScriptCoreGTK, Chromium/CEF) enters a final artifact; web content runs in Flatpak applications.
39. `/etc` in the SYSTEM image is read-only. Only an allowlist of system settings changes at runtime, through the mutable confext layer and scoped by SELinux; all other configuration arrives by snapshot or confext.
40. Interactive privilege escalation is run0 only: polkit decides who, a confined SELinux domain decides what. su, sudo and pkexec are never shipped.
41. The base exposes no interpreter a user can run other than `/bin/sh`, and human accounts get no interactive shell by default.
42. No artifact contains setuid, setgid or file-capability binaries, except `fusermount3` until a setuid-free FUSE exists.
43. Where an external specification defines a class of tools, the extension that ships them follows it (POSIX for `posix` and `posix-devel`) instead of a hand-picked list.

## 44. Summary Architecture

```
                       UPSTREAM HEADs
   FDSDK master / Linux master / systemd main / gnome-build-meta master ...
                            │
                   integration cycle (§17)
                            │
              resolve → manifest → build → test
                            │
                   ┌────────┴────────┐
                 FAIL              GREEN SNAPSHOT
               logs only             │
                                     │  latest → edge
                                     ▼  (pointers; no rebuild)
                      BEAMLINE BASE (on FDSDK + overrides)
      ┌──────────────────────────────────────┐
      │ systemd                              │
      │ glibc                                │
      │ D-Bus                                │
      │ PAM / userdb / homed                 │
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
        ┌──────────────┬────┴─────────┬──────────────────┐
        │              │              │                  │
 desktop-gnome       posix       posix-devel     printing-scanning
        │       (POSIX.1-2024,   (toolchains)     (CUPS, SANE)
        │       uutils, bash)
   GNOME Shell / GDM
   Wayland
   PipeWire
   Flatpak (apps, terminals, utilities)
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
