# Beamline Security Architecture

## Mandatory Integrity Boundaries and Code Provenance

- Status: Normative annex of [spec.md](spec.md) (spec revision 6)
- Revision: 3 (2026-10-09)
- Scope: Beamline base, Virt and Hardware profiles, RecoveryOS, system extensions,
  development environments, and CI infrastructure
- Relationship: Extends spec §5–§8 and §18–§22. Where the two disagree, this annex governs
  security matters, and spec §21, §22 and §40 summarise it.

> Adapted from the project owner's draft "MyOS Security Architecture". Changes made while
> adopting it: the OS name and policy names (MyOS → Beamline, `myos_*` → `beamline_*`); the
> disk layout of spec §15 (SYSTEM-A/B, DATA on ext4 at `/data`); the Server profile and the
> self-hosted builder chain are deferred (§20); and decisions taken with the owner on policy
> language, MCS, permissive mode, keys and staging (§16, §19).
>
> Revision 2 adds the web-engine rule (§8.2), corrects the SELinux-aware override list after
> inspecting FDSDK's builds (§19.2), and describes how extension images are labelled (§19.1).
>
> Revision 3 describes run0 and its confined admin domain (§9.4), the SELinux-scoped mutable
> `/etc` (§9.5), what Stage 1 contains (§16), which mandatory tests run in 0.0.3 (§15), and
> development-key signing of both UKIs and of modules (§19.4, §19.5). The channels are
> `latest` and `edge` (§7.1, §13.3).

---

## 1. Purpose

Beamline shall implement a mandatory integrity architecture based on hierarchical trust, authenticated platform artifacts, and strictly controlled execution authority.

The primary security objective shall be prevention of unauthorized promotion of lower-integrity code into higher-integrity execution environments.

The architecture shall permit arbitrary execution of user-provided software within appropriately confined user environments.

Cryptographic signatures, verified filesystems, and integrity measurements shall establish evidence of code provenance and authorized endorsement. Cryptographic validity alone shall not confer platform authority.

SELinux shall serve as the mandatory access-control foundation.

## 2. Fundamental Security Invariant

Let:

- `P(C)` denote the authorized integrity level of executable code `C`;
- `P(E)` denote the integrity level of execution environment `E`.

Execution shall satisfy:

`P(E) ≤ P(C)`

This is the Biba rule for execution: an environment may only run code of equal or higher integrity. Additional mandatory access-control restrictions may prohibit execution even when the ordering is satisfied.

Execution of higher-integrity code within a lower-integrity environment shall not automatically elevate process integrity, privileges, capabilities, SELinux domain, or administrative authority.

Code originating from a lower-integrity source shall not acquire higher integrity through compilation, interpretation, copying, linking, relocation, installation, or execution by a higher-integrity program.

Elevation of code integrity shall require explicit endorsement by an authorized higher-integrity authority.

The operating system shall enforce integrity ordering through SELinux policy, trusted artifact construction, executable-file controls, and constrained privileged-service design.

## 3. Integrity Levels

Beamline shall initially define four conceptual integrity levels.

| Level | Classification | Intended scope |
|---|---|---|
| P3 | Platform | Kernel, initrd, verified base, privileged Beamline services, official platform extensions |
| P2 | Delegated trusted code | Explicitly authorized third-party host components and delegated services |
| P1 | Restricted application code | Application compartments with explicitly limited authority |
| P0 | Arbitrary user code | User binaries, scripts, development containers, downloaded programs, local builds |

The integrity ordering shall be:

`P0 < P1 < P2 < P3`

P3 shall represent the highest ordinary runtime integrity level.

P2 and P1 support shall remain optional until concrete delegation requirements emerge. The initial policy implements P3 and P0.

### 3.1 Integrity and authority

Integrity level shall represent authorized code provenance.

Execution authority shall represent access to resources, capabilities, devices, service interfaces, and protected data.

Integrity level and execution authority shall remain separate security properties.

A P3 executable running inside a P0 user session shall retain P3 provenance without receiving P3 execution authority.

A P0 program may possess legitimate access to user-owned files without receiving permission to modify platform-controlled resources.

### 3.2 Compartments

Integrity ordering shall not imply unrestricted communication between domains sharing an integrity level.

SELinux types, roles, MCS categories, and filesystem permissions shall enforce isolation between unrelated principals and workloads. The policy is built with MCS from the start (§7.2), so categories are available for compartments.

A delegated P2 vendor service shall not automatically gain authority over unrelated P2 services.

A P0 workload belonging to a human account shall not automatically gain access to another account.

## 4. Threat Model

### 4.1 Protected assets

The security architecture shall protect:

- kernel execution and privileged kernel interfaces;
- verified system images and boot artifacts;
- platform executable code and libraries;
- SELinux policy and security-relevant labels;
- update, rollback, extension, and recovery control planes;
- authentication and authorization services;
- privileged service credentials;
- system-managed persistent state;
- isolation boundaries between users, applications, containers, and services;
- release signing and endorsement authority.

### 4.2 Permitted lower-integrity activity

The security model shall permit ordinary users to:

- execute arbitrary native binaries;
- run locally compiled programs;
- execute Python, shell, JavaScript, and other interpreted code;
- install software inside development containers;
- execute unsigned programs from user-controlled storage;
- run untrusted workloads inside optional isolated virtual machines.

No distribution-wide signing requirement shall apply to ordinary P0 execution.

### 4.3 Security boundary

Unauthorized P0 access to P3 code, privileged services, kernel authority, protected credentials, or higher-integrity state shall constitute a security violation.

Malicious execution confined to authorized P0 resources shall not, by itself, constitute a violation of the platform-integrity invariant.

Theft or destruction of user-accessible data shall remain a security incident, regardless of platform-integrity status.

Protection of sensitive user data from user-authorized code shall require separate application confinement, secret isolation, or explicit workload isolation.

### 4.4 Initial exclusions

Absolute protection against kernel exploitation, malicious authorized signers, compromised release infrastructure, microarchitectural attacks, and arbitrary interpreter-level code injection shall remain outside initial enforceable guarantees.

Until production Secure Boot keys exist (spec §40), every guarantee in this annex holds only against attackers who cannot change the boot configuration or kernel command line.

The architecture shall nevertheless minimize exposure to relevant attack classes.

## 5. Code Provenance and Endorsement

### 5.1 Provenance assignment

Executable artifacts shall receive integrity classifications from authenticated provenance and explicit authorization policy.

Filesystem location, executable ownership, compiler identity, or possession of a valid signature shall not independently determine integrity classification.

Unclassified mutable code shall default to P0.

### 5.2 Integrity propagation

Build outputs shall not automatically inherit the integrity level of the compiler or build host.

Unendorsed executable outputs derived from P0 source code shall remain P0.

Generated scripts, executable configuration, bytecode, plugins, dynamically loaded libraries, and compiled programs shall qualify as code-bearing artifacts.

Code-bearing inputs shall participate in provenance evaluation.

### 5.3 Explicit endorsement

Promotion of executable artifacts into P1, P2, or P3 shall require a trusted endorsement operation.

Endorsement procedures shall define:

1. the authorized endorsing principal;
2. the target integrity level;
3. the exact artifact identity or authenticated artifact collection;
4. the required validation and review;
5. the authorized deployment context;
6. a signature or equivalent tamper-resistant authorization record;
7. the revocation and replacement policy.

Successful compilation shall not constitute endorsement.

Successful malware scanning shall not constitute endorsement.

Cryptographic signing shall record an endorsement decision rather than substitute for validation.

For platform artifacts, a green integration snapshot (spec §17.2) is the validation step: its exact source manifest, controlled BuildStream graph, image construction and mandatory tests (§15) are the evidence an endorsement signs.

### 5.4 Signing authority

Signing keys shall carry explicitly defined authorization scopes.

A key authorized for P2 artifacts shall not authorize P3 execution.

Development and diagnostic keys shall not automatically authorize production platform code. Development keys are committed to the repository, labelled as such, and trusted only by development boot configurations (§19.4).

Release-signing authority shall remain isolated from ordinary CI build workers.

## 6. Trusted Platform Construction

### 6.1 Verified boot

Production platform images shall use authenticated boot artifacts and verified immutable system storage.

The intended trust chain shall include:

1. platform firmware and boot trust configuration;
2. a signed Unified Kernel Image on XBOOTLDR;
3. an authenticated kernel command line and initrd;
4. an authenticated dm-verity root hash;
5. the verified EROFS SYSTEM filesystem;
6. SELinux policy and file labels protected by verified image construction.

Authenticated filesystem contents shall include executable binaries, libraries, policy files, service definitions, and security-relevant metadata.

### 6.2 System extensions

Official sysext images shall participate in the platform endorsement process.

System extension compatibility shall remain explicitly coupled to the corresponding Beamline snapshot.

Security labels shall be assigned during image construction and protected before publication.

Extension integrity validation shall precede activation.

Merged OverlayFS views shall undergo execution-policy and label-verification testing.

A valid extension signature shall not authorize privileges outside the extension's assigned trust scope.

### 6.3 Mutable DATA

DATA shall remain independent of A/B system-image rollback.

DATA is an ext4 filesystem mounted at `/data`, with persistent `/var` and `/home` provided as bind mounts of `/data/var` and `/data/home` (spec §15).

Mutable storage shall not automatically qualify as low integrity. Integrity classification shall depend on permitted writers, authenticated contents, and SELinux policy.

However, executable artifacts stored on mutable DATA shall default to P0 without explicit higher-integrity endorsement.

Trusted services shall not execute arbitrary helpers, libraries, scripts, or plugins from writable DATA.

From Stage 1 the policy enforces this by type. Content a lower integrity level can write (DATA, homes, temporary and runtime files, `/dev/shm`, the ESP) carries types that platform and admin domains may never execute; a `neverallow`, checked when the policy is compiled, keeps any rule from granting it. The filesystem labels go further: the types of SYSTEM code may never be associated with DATA's filesystems, so no process, whatever label it chooses, can place an executable labelled as platform code on DATA.

System-managed state under `/var` shall receive service-specific SELinux types and restricted write authority.

## 7. SELinux Policy

### 7.1 Mandatory enforcement

SELinux shall be mandatory for supported production deployments.

The final Hardware and Virt production policies shall operate in enforcing mode.

Permissive mode shall remain available during development, staged integration, and explicitly authorized recovery.

Production boot profiles shall not silently disable SELinux or select permissive operation.

Enforcement mode is a property of the boot entry, not of the release channel. Under the promotion model (spec §17.3) `latest` and `edge` are the same bytes. Once a profile enforces, every snapshot's production UKI enforces. Permissive operation is reachable only through the separately signed development UKI (§19.4).

### 7.2 Policy architecture

Beamline shall maintain a small, distribution-specific SELinux policy, written from scratch in CIL (Common Intermediate Language) and compiled with `secilc`. Every rule is project-owned and reviewable.

The policy is built with MCS from the start (a single sensitivity `s0` plus categories), so that category-based compartments (§3.2) and container separation need no later relabelling. MLS remains a later evaluation (§7.5).

The policy shall define explicit domains for:

- early boot and systemd;
- device management and udev;
- journald and logging;
- network management and DNS;
- authentication and user management;
- D-Bus and polkit;
- sysupdate and image deployment;
- sysext activation;
- recovery coordination;
- machine and container management;
- desktop session components;
- human user sessions;
- privileged Beamline control services.

Example policy-domain names may include `beamline_updater_t`, `beamline_user_t`, `beamline_container_t`, and `beamline_platform_t`.

Final policy naming shall follow established SELinux conventions.

### 7.3 Domain transitions

Execution of a P3 executable by a P0 process shall not automatically enter a P3 domain.

Transitions into privileged domains shall require explicit SELinux policy authorization and controlled entrypoints.

Lower-integrity domains shall not receive direct transition permission into platform-management domains.

SELinux `neverallow` assertions shall prohibit unintended execution grants, entrypoint permissions, and privileged domain transitions. They shall also prohibit granting `setenforce` and policy loading (`load_policy`) to any domain outside an explicitly authorized recovery domain.

### 7.4 Higher-integrity executable state

Lower-integrity domains shall not modify executable files, trusted libraries, SELinux policy, service definitions, or executable configuration consumed by higher-integrity domains.

Trusted services shall not inherit executable search paths controlled by lower-integrity principals.

Trusted services shall not load libraries through user-controlled `LD_LIBRARY_PATH`, `LD_PRELOAD`, plugin directories, or equivalent mechanisms.

### 7.5 MLS evaluation

SELinux Type Enforcement shall provide the initial integrity-domain implementation.

SELinux MLS constraints may implement formal integrity ordering after successful Type Enforcement validation.

Conventional confidentiality-oriented MLS policy shall not be treated as an existing Biba integrity implementation.

Introduction of MLS shall require separate policy proofs, transition testing, and operational evaluation.

## 8. Interpreters and Dynamic Code

### 8.1 General rule

Integrity classification shall apply to interpreted code and runtime-loaded executable content, not merely interpreter binaries.

Execution of a verified interpreter shall not elevate lower-integrity scripts.

Execution of a verified dynamic loader shall not elevate lower-integrity libraries.

Compilation through a verified compiler shall not elevate lower-integrity source code.

### 8.2 Trusted platform restrictions

P3 services shall not provide general-purpose execution interfaces for arbitrary scripts, bytecode, plugins, or generated code.

Privileged services shall avoid:

- Python and other general-purpose scripting runtimes;
- shell evaluation of mutable strings;
- runtime loading of user-controlled libraries;
- user-writable plugin directories;
- arbitrary command dispatch;
- unrestricted executable-memory generation;
- dynamic evaluation of user-controlled configuration.

The base shall retain minimal POSIX shell compatibility where required (dash, spec §6). Bash shall remain outside the base.

Base systemd units shall not depend on shell pipelines or script-driven service orchestration (spec §6, enforced by `tools/check-policy.py`).

Web engines and web JavaScript engines (WebKitGTK, JavaScriptCoreGTK, Chromium/CEF) execute remote content through a JIT. That content is P0 dynamic code, so these engines are not part of the platform. No final artifact contains one: not SYSTEM, the initrd, a UKI, or an official extension (spec §7.1). Web content runs in Flatpak applications, at application integrity. `tools/check-policy.py` enforces the rule on every artifact tree.

Exceptions shall require documented execution provenance, SELinux confinement, and dedicated negative tests.

### 8.3 Interpreter cooperation

Mainline `AT_EXECVE_CHECK`, `SECBIT_EXEC_RESTRICT_FILE`, and `SECBIT_EXEC_DENY_INTERACTIVE` (Linux 6.14 and later) may strengthen authorized script execution.

Interpreter integration shall remain optional unless privileged platform requirements demand interpreted code.

Relevant interpreter binaries shall require explicit support for kernel-mediated script checks.

File-descriptor-based checks shall be preferred over path-based prechecks.

Interpreter checks shall not replace SELinux policy or trusted-service input validation.

### 8.4 Executable memory

P3 services shall avoid JIT compilation and writable executable memory.

SELinux executable-memory controls (`execmem`, `execmod`, `execstack`, `execheap`), `MemoryDenyWriteExecute=`, executable memfd restrictions, and seccomp policies shall be evaluated per service.

P0 development workloads may retain JIT and executable-memory facilities under lower-integrity confinement.

The kernel cannot automatically classify arbitrary instructions interpreted from ordinary data or generated exclusively in memory. The initial Beamline integrity guarantee shall therefore rely on exclusion of unrestricted dynamic-code mechanisms from trusted platform domains.

### 8.5 Self-sandboxing

Landlock may be used by applications and development tooling for unprivileged self-confinement. Landlock does not implement platform integrity and shall not replace SELinux.

## 9. Privileged Services and Administrative Authority

### 9.1 Administrative control plane

Administrative authority shall remain separate from unrestricted UID 0 execution.

Normal administrative operations shall use:

`Unprivileged client → authorized IPC → privileged service → narrowly defined operation`

D-Bus or Varlink shall provide service interfaces where appropriate, with names under `org.beamline` (spec §19).

Polkit shall mediate human authorization.

SELinux shall constrain privileged endpoint access independently of polkit decisions.

The normal platform shall retain locked root login and shall not require general-purpose `sudo` or `su`.

### 9.2 Request handling

Lower-integrity clients may submit data to privileged services only through explicitly authorized interfaces.

Privileged services shall:

- authenticate relevant callers;
- validate operation authorization;
- parse bounded and structured inputs;
- reject command strings requiring shell evaluation;
- reject untrusted executable paths;
- prevent unsafe deserialization;
- restrict filesystem and device access;
- avoid loading executable plugins from client-controlled storage;
- maintain service-specific SELinux confinement.

Validated input data shall not automatically receive P3 code provenance.

### 9.3 Service hardening

Applicable systemd hardening controls shall include:

- `NoNewPrivileges=yes`
- `ProtectSystem=strict`
- `ProtectHome=yes`
- `PrivateDevices=yes`
- `PrivateTmp=yes`
- `ProtectKernelTunables=yes`
- `ProtectKernelModules=yes`
- `CapabilityBoundingSet=`
- `SystemCallFilter=`
- `RestrictNamespaces=`
- `MemoryDenyWriteExecute=yes`

Service-specific functionality shall determine applicable restrictions.

### 9.4 Interactive escalation (run0)

`run0` is the only interactive escalation path (spec §19). Its authority is split:

- **Who: polkit.** run0 asks systemd to start a transient unit, so polkit sees the action `org.freedesktop.systemd1.manage-units` and the unit name, never the command. Members of `wheel` authenticate with their own password; every other subject is refused without a prompt. polkit therefore cannot scope what a run0 command does.
- **What: SELinux.** PAM's `pam_selinux` gives run0 sessions the admin domain (`admin_t`). From Stage 1 it is confined:
  - no `setenforce`, policy load or other security-class permission;
  - no kernel module loading;
  - no writes to SYSTEM or to `/etc` types outside the allowlist (§9.5);
  - no execution of files labelled as DATA, home or temporary content.

  The admin domain is P2, delegated authority: it may manage services, units and the allowlisted settings. It is never P3.
- **polkit rules are platform code.** polkit evaluates its JavaScript rules with an interpreter (duktape). Rules are read only from SYSTEM (`/usr/share/polkit-1/rules.d`); `/etc/polkit-1/rules.d` stays empty, and no mutable location feeds rules.
- `pkexec` is never shipped: a setuid general-purpose command runner contradicts §9.1.
- **Known gap (0.0.3).** run0 is a client of PID 1's transient-unit call, and so is `systemd-run`. polkit sees the same action and the same unit naming for both, and SELinux the same `system start` permission. Only run0 adds the PAM session that leads to `admin_t`, so a wheel member can start a transient service without it, which runs in `init_t`. Requiring a PAM session or the admin context on every transient unit a session requests needs a systemd change or a privileged broker (decisions D58).

### 9.5 Scoped mutable configuration

`/etc` is read-only except the allowlist in spec §14, which `systemd-confext`'s mutable layer writes on DATA. DATA is not authenticated, so the layer is untrusted at every boot. The initrd rebuilds it from the allowlisted files alone before merging it, so nothing else written into it (offline, or during a permissive boot) reaches `/etc`. The allowlisted files themselves stay validated input to the services that parse them (§9.2), never platform code. At runtime the scope is SELinux:

- each allowlisted path has its own file type (hostname and machine-info, timezone and RTC, locale and keymap, machine ID). In Stage 0 and 1 the platform domains, where the systemd settings services run, may write them; Stage 2 narrows that to the services' own domains;
- every other `/etc` type belongs to an immutable attribute. A `neverallow`, checked when the policy is compiled, keeps every domain, platform domains included, from creating, writing, renaming, unlinking or relabelling it. The one exception is the extension merger (`sysext_t`, `systemd-sysext` and `systemd-confext`): building a merged hierarchy gives its root, its work directory and its metadata the hierarchy's own types, and the merger mounts the overlay. Every write through the merged `/etc` is checked against the writing process first;
- systemd creates its temporary files with the label of the target path, so a service can replace its own file without being able to replace any other.

The scope holds in enforcing boots. The permissive development UKI does not enforce it, as with every other rule.

## 10. User Execution Environments

### 10.1 Ordinary user sessions

Human user sessions shall execute arbitrary P0 code under confined SELinux domains.

Ordinary user sessions shall not receive unrestricted platform-management authority.

SELinux user mappings shall avoid production reliance on unrestricted domains.

### 10.2 Development containers

Rootless Podman and Distrobox-style workflows may provide normal development environments. FDSDK provides podman, crun and bubblewrap.

Development containers shall remain P0 unless explicitly endorsed for a higher integrity level.

Container execution shall not imply a strong confidentiality boundary.

Shared home directories, user credentials, host sockets, graphical interfaces, and D-Bus access shall remain explicit security considerations.

Container confinement shall use SELinux (types and MCS categories), Linux namespaces, seccomp, capabilities, and resource limits where applicable.

### 10.3 Optional virtual machines

On-demand virtual machines may provide stronger isolation for untrusted workloads.

`systemd-vmspawn` and QEMU/KVM shall remain candidate implementation mechanisms.

The initial security architecture shall not require VM-backed execution for every user workload.

Isolated VM profiles should provide:

- a separate guest kernel;
- private guest home storage;
- explicit file import and export;
- restricted host-directory sharing;
- controlled network access;
- no unrestricted host D-Bus exposure;
- no implicit host credential forwarding.

VM execution shall not automatically raise code-integrity classification.

### 10.4 User data

Ordinary user execution may access user-authorized resources.

Protection against malicious access by same-user code shall require independent workload isolation, separate credentials, protected service domains, or explicit resource sharing controls.

`systemd-homed` encryption shall protect appropriate storage states without implying isolation from authenticated processes already authorized to access an unlocked home.

## 11. Kernel Integrity Boundary

Kernel authority shall remain separate from ordinary user execution.

Kernel modules, firmware, kexec images, privileged BPF programs, and related kernel-controlled resources shall receive explicit authorization policies.

Applicable mechanisms shall include:

- kernel module-signature enforcement (§19.4);
- kernel lockdown where appropriate (meaningful only with Secure Boot);
- restricted privileged BPF access (systemd itself uses BPF and needs explicit grants);
- SELinux kernel-interface permissions;
- capability restrictions;
- optional IPE provenance rules;
- verified firmware or other source authentication where supported.

Ordinary P0 processes shall not gain kernel-execution authority through local compilation or arbitrary program execution.

## 12. IPE, IMA, and Other Integrity Mechanisms

### 12.1 SELinux primacy

SELinux shall remain the primary execution-domain enforcement mechanism.

IPE and IMA shall remain complementary.

### 12.2 IPE

IPE may enforce provenance restrictions for kernel-loaded resources and selected fixed-function environments.

IPE shall not serve as the primary implementation of domain-specific integrity ordering, because current IPE policy lacks direct SELinux-domain and UID selectors.

A strict global IPE `EXECUTE` denial shall not be enabled in general-purpose Beamline profiles without proven compatibility with arbitrary P0 execution.

### 12.3 IMA appraisal

Selective IMA appraisal may require authenticated executable files for narrowly identified privileged domains or file classes.

IMA appraisal shall not be required globally for ordinary user execution.

IMA signature metadata shall not duplicate verified-root protection without a demonstrated additional security requirement.

### 12.4 IMA measurement

IMA measurement may record selected trusted execution events and critical kernel configuration for CI attestation.

Measurement collection shall not imply executable authorization.

Remote attestation shall require independent verification policy and trustworthy attestation evidence.

### 12.5 fs-verity

fs-verity may authenticate individually updated files on suitable writable filesystems.

Authenticated file digests shall require authorization policy before receiving elevated integrity classification.

## 13. Release Endorsement

### 13.1 Build environments

Compilation of arbitrary source code shall remain permitted within confined build-worker environments.

Build workers shall not receive unrestricted platform endorsement authority.

### 13.2 Release acceptance

Release artifact endorsement shall require:

1. an exact pinned source manifest;
2. a controlled BuildStream graph;
3. successful image construction;
4. the required integration and security tests;
5. artifact identity verification;
6. an authorized release decision;
7. a protected signing operation.

Items 1–5 are what a green integration snapshot already establishes (spec §17). Items 6 and 7 are the endorsement.

Signing authority shall remain separate from disposable build workers.

### 13.3 Release channels

`latest` and `edge` shall remain promotion pointers to immutable snapshot artifacts.

Channel promotion shall represent release maturity and qualification, not automatic elevation of executable integrity provenance.

Integrity endorsement and release-channel eligibility shall remain distinct policy decisions.

## 14. Update, Rollback, and Recovery

### 14.1 A/B updates

SYSTEM-A and SYSTEM-B (spec §15) shall contain independently authenticated system deployments, each booted through its own signed UKI on XBOOTLDR.

Boot selection shall not bypass SELinux enforcement or platform integrity validation.

Rollback shall restore an approved executable platform state without automatically rolling back mutable DATA.

Persistent-state compatibility shall be tested independently.

### 14.2 Security revocation

Valid signatures shall establish artifact authenticity but shall not independently establish acceptable security freshness.

Security revocation and minimum-version enforcement shall remain separate policy concerns.

Rollback restrictions shall account for emergency recovery requirements.

### 14.3 RecoveryOS

RecoveryOS shall use a separate signed boot environment. It is a stub today (spec §20), and these rules apply when it becomes real.

Recovery authority shall not depend on unrestricted ordinary-user execution.

Recovery privileges shall be documented and separated from the normal platform control plane.

A recovery mechanism shall not silently elevate ordinary P0 code into P3 execution.

## 15. Mandatory Security Tests

CI shall include positive and negative enforcement tests. They run in the Virt profile as part of integration cycles. Tests needing interpreters or compilers (absent from the base by design) run them from a test-only extension or a P0 container, never from the base image.

| Test | Expected result |
|---|---|
| P0 executes arbitrary unsigned ELF | Allowed |
| P0 executes arbitrary Python script | Allowed |
| P0 executes verified `beamlinectl` | No privileged domain transition |
| P0 requests authorized update through IPC | Permitted after authorization |
| P0 requests unauthorized update | Denied |
| P0 modifies verified `/usr` contents | Denied or integrity failure |
| P0 writes privileged service executable state | Denied |
| P0 directly enters `beamline_updater_t` | Denied |
| P3 updater executes `/var/tmp/helper` | Denied |
| P3 updater loads user-controlled library | Denied |
| P3 updater evaluates user-controlled script | Denied |
| P0 loads unauthorized kernel module | Denied |
| P0 performs unauthorized privileged BPF loading | Denied |
| Any domain other than authorized recovery calls `setenforce` | Denied |
| Official authenticated sysext activates | Allowed |
| Tampered sysext activates | Denied |
| P0 executes software inside confined development container | Allowed |
| P0 container accesses unauthorized host resource | Denied |
| P0 accesses another user's protected files | Denied |
| Previous approved deployment boots after rollback | Allowed under rollback policy |
| Production UKI boots with SELinux disabled or permissive | Release validation failure |

Security testing shall inspect actual SELinux contexts, domain transitions, executable mappings, audit records, and service permissions.

In 0.0.3 (Stage 1) integration cycles run these tests: arbitrary unsigned ELF; modification of verified `/usr`; writes to privileged executable state and to non-allowlisted `/etc`; direct entry into the updater and admin domains; the updater executing `/var/tmp/helper`; unsigned module loading; `setenforce`; authorized and unauthorized update requests; signed and tampered sysext activation; another user's files (refused by file permissions and homed's encryption: Stage 1 does not separate users by type or category); rollback; and the production UKI's enforcing mode. `ci/test-security` runs the checks that must be refused as root, so that SELinux, not file permissions, is what refuses them. These tests are deferred, with their reason:
- the Python script, because no artifact ships an interpreter (a test extension or P0 container follows);
- privileged BPF loading, because no artifact ships BPF tooling;
- `beamlinectl`, the updater's library and script loading, and containers, which wait for the components they exercise (Stage 2).

The policy's `neverallow` rules, checked at compile time, cover the transition grants these tests would otherwise probe.

Unexpected SELinux AVC denials shall block promotion until explicitly resolved. From Stage 1, an integration cycle with an unexpected AVC denial is not green (spec §17.2). In Stage 0, the manifest records AVC denials without gating on them.

Policy changes shall require regression testing against prohibited grants.

## 16. Deployment Stages

### Stage 0 — Initial integration (with milestone 0.0.2)

- Kernel built with SELinux; base userspace (systemd, PAM, dbus-broker) built SELinux-aware. util-linux and shadow follow later (§19.2).
- The CIL policy, with MCS, compiles and loads; platform and user domains and executable file types are defined. Stage 0 declares the object classes the platform uses and sets `handleunknown allow`. Stage 1 declares the kernel's full class map and denies unknown classes.
- The EROFS SYSTEM image and extensions are labelled at construction (§19.1); DATA is labelled at runtime.
- The Virt profile runs permissive; integration cycles record AVC denials.

### Stage 1 — Virt enforcement (with milestone 0.0.3)

- The Virt production UKI enforces. The permissive development UKI ships in every snapshot (§19.4).
- Platform and user separation, and privileged-service entrypoints.
- The mandatory negative tests (§15) run in integration cycles.
- Zero unexpected AVC denials becomes part of "green".
- Arrives together with dm-verity, signed UKIs and development keys, so enforcement cannot be undone by editing the command line on a development-key system.
- Policy contents in 0.0.3:
  - the full kernel class map with `handleunknown deny`;
  - platform domains (`init_t` and the services it starts), with the settings writers (hostnamed, timedated, localed), the updater (`sysupdate_t`), homed (`homed_t`) and the extension merger (`sysext_t`, §9.5) in their own domains. Platform domains never execute content a lower level can write (§6.3);
  - `admin_t` for run0 (§9.4);
  - `user_t` for human sessions (P0). It keeps `execmem`, because P0 code may use a JIT (§8.4); GNOME Shell's JavaScript engine runs there.

  Other services stay in `init_t` until Stage 2 confines them. Expected denials (those the negative tests provoke) are listed with a reason; any other denial fails the cycle.

### Stage 2 — Hardware enforcement (after milestone 0.1)

- Extend enforcement to physical hardware.
- Confine network, authentication, graphical, and service-management components.
- Enable rootless development-container integration.
- Validate authenticated sysext labelling and activation.

### Stage 3 — Privileged execution hardening

- Restrict executable mappings and mutable code paths in platform domains.
- Enforce kernel-module signing with production keys and kernel-interface policy.
- Evaluate narrow IPE and IMA requirements.
- Establish secure endorsement and revocation procedures with production keys.

### Stage 4 — Advanced integrity

- Evaluate SELinux MLS-based integrity ordering.
- Evaluate per-artifact fs-verity and selective IMA appraisal.
- Add optional isolated VM workloads.
- Extend provenance verification to remote attestation.

## 17. Architectural Invariants

1. Lower-integrity code shall not execute with higher-integrity execution authority.
2. Execution of trusted code shall not automatically elevate an untrusted caller.
3. Compilation and interpretation shall not automatically elevate code provenance.
4. Integrity endorsement shall require explicit authorization.
5. Cryptographic verification shall establish evidence, not policy authority.
6. SELinux shall enforce the primary host integrity boundary.
7. Privileged services shall not execute arbitrary mutable code.
8. Ordinary users shall remain free to execute arbitrary software under confined authority.
9. System extensions shall not bypass platform endorsement or SELinux policy.
10. Kernel execution interfaces shall remain explicitly restricted.
11. Persistent DATA shall not acquire platform trust through filesystem location alone.
12. Release signing shall remain separate from ordinary compilation authority.
13. Recovery shall not bypass integrity policy without explicit recovery authorization.
14. Integrity classification shall remain separate from confidentiality and resource-access authority.
15. Security guarantees shall reflect actual kernel enforcement and verified userspace behavior.
16. Enforcement mode belongs to the boot entry, not to the release channel; production UKIs of an enforcing profile always enforce.

## 18. Acceptance Criteria

The architecture shall qualify for production enforcement following demonstrated satisfaction of four requirements:

**Platform integrity:** Unauthorized modification or replacement of trusted platform code shall fail.

**Execution integrity:** Lower-integrity code shall not execute inside higher-integrity platform domains.

**User flexibility:** Arbitrary P0 executable code shall remain usable within authorized user and development environments.

**Boundary enforcement:** Lower-integrity execution shall not bypass SELinux-mediated authority, protected service interfaces, or kernel security restrictions.

Complete provenance tracking across arbitrary interpreted languages, JIT-generated instructions, and general-purpose data processing shall not constitute an initial production guarantee.

The long-term security objective shall remain a verifiable mandatory integrity hierarchy with explicit code endorsement and narrowly constrained trust-boundary crossings.

## 19. Implementation Constraints

These are facts of the current toolchain that the stages above must work with. They were established when this annex was adopted (2026-10, FDSDK master `c67967f`, BuildStream 2.8.1, Linux 7.3-rc).

### 19.1 Labels are applied when filesystems are created

BuildStream artifacts do not preserve extended attributes, and the build sandbox cannot store them. SELinux labels can therefore never be carried through the build graph. They are applied by the tool that creates each filesystem image, from the policy's `file_contexts`:

- **EROFS SYSTEM image:** `mkfs.erofs --file-contexts`, which requires erofs-utils built `--with-selinux`. FDSDK's build lacks it, so this needs an override. `systemd-repart` creates the SYSTEM partition and passes the option through `SYSTEMD_REPART_MKFS_OPTIONS_EROFS`.
- **Extension images (sysext and confext):** the same `mkfs.erofs --file-contexts`, run on the extension tree. Its paths are the paths the files take after merging (`/usr/...`, `/etc/...`), so the same `file_contexts` applies. OverlayFS passes the lower files' labels through after merging.
- **ESP and XBOOTLDR (vfat):** no labels; the policy assigns them through `genfscon`/mount context.
- **DATA (`/data`, ext4):** labelled at runtime by systemd, never at build time. tmpfiles labels what it creates, and `z`/`Z` lines relabel the few entries the image build places on DATA (the directory skeleton and extension images).
- **initrd (cpio):** cpio carries no labels. The initrd is a trimmed copy of the root (spec §13), so image assembly removes the policy (`/etc/selinux`) from it. The policy is loaded only by systemd in the host, after switch-root.

### 19.2 SELinux-aware userspace needs overrides

FDSDK provides `libselinux` and `libsepol`, but builds its consumers without SELinux. Inspecting the built image (FDSDK master `c67967f`) showed that only `libdevmapper` links libselinux:
- systemd: `-Dselinux=disabled` (Beamline's override flips it);
- linux-pam (`linux-pam-base`): `-Dselinux=disabled`, so `pam_selinux` is not built;
- dbus-broker: SELinux off by default;
- erofs-utils: built without `--with-selinux`;
- util-linux: no libselinux in the sandbox;
- shadow: `--without-selinux`.

Stage 0 enables SELinux in systemd, linux-pam-base, dbus-broker and erofs-utils through drift-checked element overrides (spec §31.4). Two are deferred, with reasons:
- **util-linux.** An override of `util-linux-libs` would change the cache key of most of FDSDK's reverse dependencies and rebuild them locally. libmount's SELinux support (context mount options) is not needed while permissive. It is revisited for Stage 1.
- **shadow.** Its SELinux code labels files that `useradd` and friends create. With a read-only `/etc` (spec §14), they never run on a Beamline system.

In parallel, the project proposes an FDSDK build option upstream, so the overrides can be retired.

FDSDK has no policy toolchain. `secilc` (to compile the CIL policy) and `setfiles` (to validate `file_contexts`) are built by a project-owned, build-only element from SELinux userspace `main`. They never ship; the runtime libselinux remains FDSDK's.

### 19.3 Kernel configuration

The Virt kernel is built from `allnoconfig` (spec §11.4), so every security feature is an explicit fragment entry:
- `SECURITY`, `SECURITY_SELINUX`, `AUDIT`, and the security xattr handlers of EROFS, ext4 and tmpfs;
- `SECURITY_LANDLOCK` and `SECURITY_IPE` for the optional mechanisms;
- the LSM order.

`SECURITY_SELINUX_DEVELOP` is required, because the development UKI's `enforcing=0` depends on it. `SECURITY_SELINUX_BOOTPARAM` stays off, so `selinux=0` is ignored. The `lsm=` parameter can still change the LSM order and leave SELinux out, however. Production protection therefore rests on two things: the signed command line, and a policy that grants `setenforce` to no production domain (§7.3).

### 19.4 Keys, development UKI and module signing under the promotion model

- **Development keys** for UKI signing, module signing, extension verity signatures and update signatures are committed to the repository (`files/keys/dev`), one key per scope (§5.4), labelled development-only, and used by builds anywhere. Builds stay reproducible. Production keys never enter the repository or a build worker.
- **Until production keys exist**, the production UKI is signed with the development key as well. What distinguishes the two UKIs in 0.0.3 is the command line, not the key.
- **The permissive development UKI.** Every snapshot ships one: the same kernel and initrd as the production UKI, with `enforcing=0` in its signed command line, signed only with the development key. Production Secure Boot trust excludes the development key, so the development UKI cannot boot on a production-trust machine.
- **Module signing.** For now, modules are signed during the kernel build with the committed development key (`MODULE_SIG`, `MODULE_SIG_FORCE`). Because every channel ships the same kernel bytes, that kernel trusts development-signed modules in every channel, including `edge`. This is acceptable only while no production deployments exist. Stage 3 replaces it: the kernel embeds only a production public certificate, and modules are signed in a separate endorsement step outside the build graph.
- **No Virt modules.** The Virt kernel keeps loadable-module support but currently ships no modules at all, so in Virt module signing (`MODULE_SIG_FORCE`) only constrains what could be loaded later.

### 19.5 Verified boot dependency

Until Secure Boot with production keys exists (spec §40), the boot loader's command-line editor and unsigned boot entries can bypass enforcement. Once Stage 1 enforces, the systemd-boot editor is disabled. 0.0.3 signs UKIs and systemd-boot but does not enforce Secure Boot in its QEMU tests; without it, a host that controls the firmware or the SMBIOS command-line extras can still boot permissive. Guarantees are stated against that limitation (§4.4).

## 20. Deferred

These parts of the original draft are deferred, expected around version 3, and are not requirements of this revision:

- a Server profile;
- self-hosted construction of successor snapshots, and the generational builder chain with fallback to older builders and a protected bootstrap checkpoint;
- the related attestation of self-hosted CI.

Until then the builder stays pinned Layer 0 tooling outside the source graph (spec §31.3).

## References

- Beamline [spec.md](spec.md), §5–§8, §15–§22, §31, §42.
- Linux kernel documentation: [Integrity Policy Enforcement](https://docs.kernel.org/admin-guide/LSM/ipe.html).
- Linux kernel documentation: [IMA policy interface](https://github.com/torvalds/linux/blob/master/Documentation/ABI/testing/ima_policy).
- Linux kernel documentation: [Executability checks](https://docs.kernel.org/userspace-api/check_exec.html).
- Linux kernel documentation: [dm-verity](https://docs.kernel.org/admin-guide/device-mapper/verity.html).
- Linux kernel documentation: [fs-verity](https://docs.kernel.org/filesystems/fsverity.html).
- Linux kernel documentation: [Landlock](https://docs.kernel.org/security/landlock.html).
- SELinux userspace: [CIL reference](https://github.com/SELinuxProject/selinux/tree/main/secilc/docs).
