# Release model: rationale

> Design rationale for the release model in [spec.md](spec.md) §16, §17 and §31, kept verbatim as
> written by the project owner. Where this text explores alternatives, the spec states what was chosen.
> It predates the name: "MyOS" and `myos` below mean Beamline.




Yes. The earlier `nightly → canary → edge → stable` model is too conventional for this project. It quietly turns the project into a normal rolling distribution with progressively older source selections, when the more interesting goal is:

> **Track upstream HEAD aggressively, continuously integrate it, and publish every source state that proves itself bootable.**

The distinction should therefore be **integration status**, not stability tier.

## A better model: HEAD → green snapshot

The pipeline should look more like:

```text
systemd main ─────┐
Linux master ─────┤
Mesa main ────────┤
PipeWire master ──┤
WirePlumber main ─┤
labwc master ─────┤
wlroots master ───┤
iwd master ───────┤
BlueZ master ─────┘
        │
        ▼
 resolve current HEADs
        │
        ▼
 exact source-set manifest
        │
        ▼
       build
        │
        ▼
 integration tests
        │
   ┌────┴────┐
   │         │
 FAIL       GREEN
   │         │
   ▼         ▼
ephemeral  publish
CI result  snapshot
```

There is no special "stable source set."

A published image represents:

> "This was approximately upstream HEAD everywhere at time T, and this exact combination passed the project's integration criteria."

That's much closer to the identity of the project.

### "Bleeding edge" still shouldn't mean unpinned

A particular installation should never literally build or update from unresolved branch names.

Instead, an integration run at 20:00 might resolve:

```text
systemd     8f93ca8...
linux       f71852c...
mesa        c288f12...
pipewire    12fbbc0...
wireplumber aa2901e...
labwc       87e2d45...
wlroots     7ac3921...
```

That complete tuple becomes immutable:

```text
snapshot-20261007.2000
```

So the project gets both properties:

```text
source policy:
    track HEAD

artifact policy:
    pin absolutely everything
```

That's the combination worth optimizing for.

## No nightly either, really

"Nightly" is just an implementation cadence.

There is no reason an image built at midnight deserves special status.

Call the process something like an **integration cycle**:

```text
every N hours
or
manually
or
after detected upstream changes
        ↓
resolve upstream heads
        ↓
build source set
```

If nothing changed:

```text
no build
```

If the build fails:

```text
record failure
retain logs briefly
latest published snapshot unchanged
```

If everything passes:

```text
publish new green snapshot
```

The result could easily be:

```text
Monday:
    4 attempts
    2 failures
    2 snapshots

Tuesday:
    no relevant upstream changes
    0 snapshots

Wednesday:
    6 attempts
    1 snapshot
```

That's more meaningful than forcing one artifact per calendar day.

---

# Three concepts are enough

I'd reduce the whole release vocabulary to:

| Concept | Meaning |
|---|---|
| **Integration** | Attempt to build current upstream HEADs; ephemeral |
| **Snapshot** | A fully-green integration result; installable and immutable |
| **Checkpoint** | A snapshot deliberately retained long-term |

That's it.

No Canary.

No Edge.

No Stable.

A user normally tracks:

```text
latest-green
```

which points to:

```text
snapshot-20261007.2000
```

A few hours later it might point to:

```text
snapshot-20261008.0130
```

provided that source set passed everything.

The previous snapshot remains available for rollback.

## `latest-green` is effectively the release channel

But critically, it doesn't mean:

> newest reasonably stable branch.

It means:

> newest successfully integrated HEAD snapshot.

That's very different.

A machine could report:

```text
MYOS_SNAPSHOT=20261007.2000
MYOS_SOURCE_MANIFEST_SHA256=...
```

and an updater asks only:

```text
latest-green > currently installed?
```

---

# What if HEAD breaks?

This is where the philosophy becomes interesting.

Suppose:

```text
systemd HEAD       good
Linux HEAD         good
Mesa HEAD          broken
PipeWire HEAD      good
```

The integration fails.

Don't automatically substitute yesterday's Mesa and publish:

```text
everything HEAD except Mesa
```

because then "latest-green" gradually turns into an undocumented mixture of stale components.

Instead:

```text
latest-green:
    snapshot-20261007.0800

current HEAD integration:
    FAILED
    Mesa regression
```

And the published image simply doesn't advance until:

```text
Mesa fixes HEAD
```

or a deliberate project decision introduces a temporary exception.

This makes upstream breakage visible rather than silently hidden.

### Temporary pins can exist, but should look embarrassing

Sometimes an upstream regression may remain unfixed for a week.

A temporary pin is reasonable, but the manifest should loudly record:

```text
mesa:
    tracking: main
    upstream_head: abcdef1
    selected:      1234567
    status: PINNED_DUE_TO_REGRESSION
    issue: #493
    behind: 37 commits
```

The project's dashboard could expose:

```text
HEAD conformity: 7 / 8 components
```

That is much more aligned with the project's goals than calling such a release "stable."

---

# Make freshness measurable

This project could actually make **upstream freshness an explicit release metric**.

Every snapshot could contain something like:

```json
{
  "snapshot": "20261007.2000",
  "generated": "2026-10-07T20:00:00Z",

  "components": {
    "systemd": {
      "branch": "main",
      "commit": "8f93ca8",
      "head_at_resolution": "8f93ca8",
      "lag_commits": 0
    },

    "linux": {
      "branch": "master",
      "commit": "f71852c",
      "head_at_resolution": "f71852c",
      "lag_commits": 0
    },

    "mesa": {
      "branch": "main",
      "commit": "c288f12",
      "head_at_resolution": "c288f12",
      "lag_commits": 0
    }
  }
}
```

That's a much more useful statement about this OS than:

```text
Stable
Testing
Unstable
```

A core project target could even be:

> No tracked component should normally remain behind its designated upstream branch for more than 24 hours.

That defines "bleeding edge" operationally.

---

# Kernel policy fits this too

The earlier:

```text
release
rc
main
```

kernel channels also become less necessary if Linus's tree is genuinely the intended target.

The normal Virt build can simply use:

```text
linux.git master HEAD
```

resolved during each integration cycle.

Then perhaps a **checkpoint build** occasionally coincides with:

```text
v7.3-rc4
v7.3-rc5
v7.3
```

but those tags are metadata, not separate OS channels.

For example:

```text
snapshot-20261008.0600

Linux:
    commit: abcdef
    nearest-tag: v7.3-rc4-218-gabcdef
```

That is refreshingly literal.

The kernel used is simply whatever Linus had integrated when the snapshot was resolved.

---

# GitHub Releases then become much simpler

If GitHub Releases remain the primary binary store, I'd publish **every green snapshot**.

For example:

```text
snapshot-20261007.0200
snapshot-20261007.1400
snapshot-20261008.0130
snapshot-20261009.0445
```

All marked as prereleases so GitHub's normal "latest stable software release" semantics don't imply anything meaningful about MyOS.

Each contains the entire coherent build set:

```text
manifest.json

virt-aarch64.root.raw.zst
virt-aarch64.efi

virt-x86_64.root.raw.zst
virt-x86_64.efi

hardware-aarch64.root.raw.zst
hardware-aarch64.efi

hardware-x86_64.root.raw.zst
hardware-x86_64.efi

desktop-aarch64.raw.zst
desktop-x86_64.raw.zst

SHA256SUMS
SBOM
provenance
```

Then have:

```text
latest-green.json
```

point to the newest one.

---

# Prune snapshots aggressively

Because these aren't conventional releases, there is no reason to retain every green build forever.

For example:

```text
all green snapshots:
    retain 14–30 days

checkpoint snapshots:
    retain forever

currently installed/fallback snapshots:
    retain

snapshots referenced by open regressions:
    optionally retain
```

So:

```text
Oct 01  snapshot A     deleted eventually
Oct 02  snapshot B     deleted eventually
Oct 03  snapshot C     CHECKPOINT → permanent
Oct 04  snapshot D     deleted eventually
...
Oct 17  snapshot Q     current
```

The Releases page stays somewhat busy, but that's truthful: this is a continuously integrated operating system.

GitHub Releases becomes essentially a **binary snapshot registry**.

---

# Checkpoints replace "stable releases"

A checkpoint should not mean:

> this uses old, conservative software.

It should mean:

> this particular HEAD snapshot was unusually useful and is worth keeping.

Reasons might include:

```text
first physical-hardware release
first SELinux-enforcing release
first systemd 263 snapshot
first Linux 7.4 snapshot
known-good conference/demo image
pre-major-architecture-change fallback
```

For example:

```text
checkpoint-2026.11-systemd263
    ↓
refers to
    ↓
snapshot-20261104.1030
```

No rebuilding.

No changing dependencies.

Just mark that snapshot as durable.

---

# Keep a few automatic rollback generations

On installed machines, `latest-green` should not imply reckless garbage collection.

A machine might retain:

```text
current:
    20261009.0445

previous:
    20261008.0130

previous-2:
    20261007.1400
```

Then:

```text
update to HEAD snapshot
        ↓
boot regression
        ↓
choose previous UKI/root
```

That is enough safety without defining a conservative distribution channel.

The update philosophy becomes:

> Move forward as soon as HEAD passes integration; move backward instantly if reality proves CI insufficient.

That fits an experimental system much better.

---

# There is still room for one special image

The only thing I'd deliberately keep conservative is:

```text
Recovery
```

Not "stable MyOS."

A **Recovery UKI** can move slowly and use a known-good kernel/userspace because its purpose is to recover the actual bleeding-edge installation.

So the ecosystem becomes:

```text
                   Upstream HEADs
                        │
                        ▼
                 integration cycle
                        │
               ┌────────┴────────┐
               │                 │
              fail              pass
               │                 │
          diagnostics       GREEN SNAPSHOT
                                 │
                  ┌──────────────┴─────────────┐
                  │                            │
             latest-green                  checkpoint
               moving                      permanent
                  │
                  ▼
             installed OS


Separate:
    Recovery UKI
    deliberately boring
```

That contrast is healthy.

The main operating system can be absurdly fresh because a known-good rescue mechanism exists outside it.

---

## This also gives the project a sharper identity

Rather than:

> another immutable distro with stable/testing/unstable channels

the project becomes:

> **A continuously integrated desktop operating system built directly from current upstream Linux components. Every published system image is an immutable, reproducible snapshot of upstream HEADs that passed end-to-end OS integration testing.**

That is considerably more distinctive.

The unit of release isn't a version, distro branch, or package repository state.

It's a **green integration snapshot**.

And given the original goals discussed throughout the design, that is the model I'd choose.

They fit together cleanly if **“bleeding edge” and “stable” describe different axes**.

The mistake would be to make them different source universes from the beginning. Instead:

> **Snapshots describe what was built. Channels describe how much confidence exists in a snapshot.**

So the permanent foundation remains the bleeding-edge integration stream.

```text
upstream HEADs
      │
      ▼
integration attempt
      │
      ├── fail → logs only
      │
      └── pass
            │
            ▼
      immutable snapshot
      20261007.2000
```

Then several moving pointers can refer to those immutable snapshots:

```text
latest-green ───────────────► snapshot 107
edge ───────────────────────► snapshot 103
stable ─────────────────────► snapshot 88
```

Nothing gets rebuilt during promotion.

## Four concepts rather than four distributions

I would define them this way:

| Name | Meaning |
|---|---|
| `latest-green` | Newest HEAD-derived snapshot passing mandatory CI |
| `edge` | Recent green snapshot that survived additional testing/short soak |
| `stable` | Older green snapshot deliberately blessed after longer real-world validation |
| `checkpoint` | Snapshot retained permanently for historical/recovery reasons |

All four can originate from exactly the same upstream-HEAD build pipeline.

For example:

```text
Oct 1
HEAD → snapshot 100 ✓
latest-green = 100

Oct 2
HEAD → snapshot 101 ✓
latest-green = 101

Oct 3
HEAD → snapshot 102 ✗
nothing published

Oct 4
HEAD → snapshot 103 ✓
latest-green = 103
edge = 100

Oct 8
HEAD → snapshot 107 ✓
latest-green = 107
edge = 103
stable = 100
```

Snapshot 100 did not become “more conservative” when promoted.

It is still exactly the weird bleeding-edge source combination originally built on October 1.

It simply accumulated evidence that it works.

---

# This makes `stable` mean something different

Traditional distro stable means approximately:

> older upstream versions + backports + deliberate API freeze.

This project's initial stable channel could instead mean:

> **a previously bleeding-edge snapshot with unusually high confidence.**

That is a much better fit.

So:

```text
traditional distro:

unstable source set
       ↓
different stable source set


this project:

HEAD source set
       ↓
green immutable snapshot
       ↓
time/testing
       ↓
same bytes become stable
```

That distinction should probably be documented explicitly.

A name like `validated` might actually be less misleading than `stable`, although `stable` is more familiar.

---

# Edge becomes a useful middle ground

`edge` could mean:

> latest snapshot that survived all automated tests plus perhaps 24–72 hours of actual use.

For example:

```text
latest-green
    ├── QEMU boot
    ├── desktop
    ├── sysupdate
    ├── SELinux
    └── basic hardware CI

edge
    everything above
    +
    48h without blocker
    +
    selected physical machines
```

Stable could add:

```text
stable
    edge requirements
    +
    one or two weeks of use
    +
    no known critical regression
    +
    hardware qualification
```

Again:

```text
latest-green → edge → stable
```

is movement of **trust**, not movement of source code.

---

# A concrete example

Suppose a snapshot contains:

```text
snapshot = 20261114.0415

Linux:
    7.5-rc1-437-g91abcd

systemd:
    main @ f53c21d

Mesa:
    main @ ab319d2

PipeWire:
    master @ c440819

labwc:
    master @ 82a3e88
```

On November 14:

```text
latest-green = 20261114.0415
```

On November 16, after testing:

```text
edge = 20261114.0415
```

On November 27, perhaps:

```text
stable = 20261114.0415
```

Meanwhile `latest-green` might already be:

```text
20261127.1810
```

with Linux 7.5 final and dozens of newer commits elsewhere.

The stable installation is therefore about two weeks behind upstream HEAD, but it is not built from a specially conservative package branch.

That's an elegant compromise.

---

# The channel metadata could be extremely simple

Something like:

```json
{
  "latest-green": "20261127.1810",
  "edge": "20261124.0930",
  "stable": "20261114.0415",
  "recovery": "20261030.1200"
}
```

Each value identifies an immutable GitHub Release.

Then machines subscribe to one pointer:

```text
/etc/myos/channel

latest-green
```

or:

```text
edge
```

or:

```text
stable
```

Changing channel doesn't fundamentally change the updater.

It changes which signed pointer gets resolved.

---

# Switching channels should work both ways

This design makes:

```text
stable → edge
```

easy.

The machine simply sees a newer snapshot.

Likewise:

```text
edge → latest-green
```

is straightforward.

The interesting case is:

```text
latest-green → stable
```

when stable points to an older snapshot.

I would **not automatically downgrade**.

Instead:

```text
myos channel stable
```

would mean:

> Future updates follow Stable once Stable advances beyond the currently installed version.

And an explicit:

```text
myos rollback-to-channel stable
```

or recovery operation would be required for actual downgrade.

That prevents surprising rollback of user machines.

---

# Eventually there may be two meanings of stable

This is where the design can evolve.

### Phase 1: promotion-only stable

This is the model above.

```text
HEAD
 ↓
snapshot
 ↓
edge
 ↓
stable
```

No separate source branch.

I would strongly recommend starting here.

### Phase 2: maintained stable line

If the project later gets enough users, there may be demand for:

> Keep this stable snapshot for three months, but fix CVEs and catastrophic bugs.

At that point a genuinely separate maintenance line appears.

For example:

```text
HEAD integration
    │
    ├── snapshot 250
    ├── snapshot 251
    └── snapshot 252

stable/2027.02
    │
    └── based on snapshot 219
          +
          security fix A
          +
          kernel fix B
```

Now Stable is no longer byte-identical to the original snapshot.

That's a major architectural threshold.

I would not cross it accidentally.

---

# Give that maintained line a different identity

Once backports exist, don't pretend it is just a promoted snapshot.

Use something like:

```text
snapshot:
    20270203.0410

maintained release:
    2027.02.0
    2027.02.1
    2027.02.2
```

Then:

```text
2027.02.0
    derived from snapshot 20270203.0410

2027.02.1
    same base
    + CVE fix
    + regression fix
```

That clearly tells users that:

```text
snapshot 20270203.0410
```

and:

```text
stable 2027.02.1
```

are no longer identical artifacts.

This avoids contaminating the elegant HEAD-snapshot model.

---

# The repository can accommodate both models

Eventually:

```text
main
    HEAD-tracking integration policy

release/2027.02
    optional maintenance branch
```

`main` continues moving very aggressively:

```text
systemd HEAD
Linux HEAD
Mesa HEAD
...
```

while:

```text
release/2027.02
```

changes only for:

```text
security fixes
serious hardware regressions
critical correctness fixes
```

But that branch should exist **only after actual demand appears**.

Until then, maintaining it creates a lot of work and weakens the project's focus.

---

# Edge probably never needs a source branch

Even in the mature model, I'd keep Edge as pure promotion.

```text
HEAD
 ↓
green snapshot
 ↓
edge
```

Stable is the only channel that might someday justify a maintenance branch.

Thus a mature release architecture could be:

```text
                        UPSTREAM HEAD
                             │
                             ▼
                       integration
                             │
                          green?
                             │
                             ▼
                         SNAPSHOT
                             │
                 ┌───────────┴───────────┐
                 │                       │
          latest-green                 soak
                                         │
                                         ▼
                                       EDGE
                                         │
                                  longer validation
                                         │
                       ┌─────────────────┴─────────────┐
                       │                               │
                promotion-only                   fork release
                       │                               │
                       ▼                               ▼
                    STABLE                       STABLE/LTS
                   pointer                     maintenance branch
```

The left path can remain the default indefinitely.

---

# GitHub Releases map nicely onto this

GitHub Release tags could continue to be exclusively immutable snapshot identities:

```text
snapshot-20261114.0415
snapshot-20261115.0822
snapshot-20261118.2010
```

No moving:

```text
stable
edge
latest
```

Git tags are necessary.

Instead, signed channel metadata says:

```text
latest-green → snapshot-20261118.2010
edge         → snapshot-20261115.0822
stable       → snapshot-20261114.0415
```

A promoted snapshot need not be duplicated as another Release.

For human presentation, the stable target can be marked prominently in documentation or exposed as the repository's recommended/latest release, but the binary identity remains its snapshot ID.

---

# Retention rules become important

Once Edge/Stable exist:

```text
ordinary green snapshots
    retain 14–30 days

snapshot referenced by latest-green
    retain

snapshot referenced by edge
    retain

snapshot referenced by stable
    retain

checkpoint
    retain forever

maintained stable releases
    retain forever
```

Before deleting anything:

```text
is referenced by any channel?
    YES → retain

is checkpoint?
    YES → retain

otherwise old enough?
    YES → delete
```

So channel promotion automatically protects an otherwise expiring image.

---

# This model also gives users meaningful choices

The audience becomes:

**`latest-green`**

> Upstream development is the product. Temporary breakage is acceptable.

Typical developer/upstream contributor.

**`edge`**

> Extremely fresh upstream code is desirable, but a broken workstation tomorrow morning is inconvenient.

Probably the sweet spot for enthusiasts.

**`stable`**

> The architecture is desirable, including immutable images and modern components, but updates should have substantial field testing.

Normal users, eventually.

And all three still use much fresher code than most traditional distributions because Stable starts from a HEAD snapshot rather than a conservative distro branch.

---

## An especially nice consequence

Suppose a new kernel introduces a disastrous laptop regression.

State:

```text
latest-green = 315
edge         = 309
stable       = 288
```

CI doesn't cover the particular laptop, so snapshot 315 got published.

After reports arrive:

```text
latest-green = 315   ← technically remains latest green
edge         = 309
stable       = 288
```

The project can annotate:

```text
315: known regression on hardware X
```

and simply **refuse to promote it**.

Snapshot 316 or 317 eventually fixes the problem.

No emergency rebuilding of Edge or Stable is necessary.

The promotion barrier did exactly what it was supposed to do.

---

# The project philosophy then becomes two-dimensional

This is the cleanest way to describe the whole thing:

```text
                     SOURCE FRESHNESS
                           │
                           │
                    always very high
                           │
                           ▼

             HEAD-derived immutable snapshots


      CONFIDENCE / VALIDATION AGE
                    │
       ┌────────────┼────────────┐
       │            │            │
latest-green       edge        stable
   hours          days        weeks
```

Traditional distributions often move **both axes** together:

```text
unstable = new
stable   = old
```

This project doesn't have to.

All channels can remain fundamentally bleeding-edge.

They merely differ in **how long the exact snapshot has survived reality**.

That preserves the project's original identity while leaving a very natural path toward an Edge or Stable offering later.

Yes. That feels like the cleanest expression of the project.

The important shift is to stop thinking of the OS as a collection of independently versioned packages and instead treat the **entire resolved source graph as one integrated object**:

```text
systemd HEAD
Linux HEAD
Mesa HEAD
PipeWire HEAD
Wayland HEAD
labwc HEAD
...
      │
      ▼
resolve exact commits
      │
      ▼
BuildStream graph
      │
      ▼
     OS snapshot
      │
      ▼
integration tests
```

If that particular combination passes, the resulting image is a valid release candidate. Whether Linux happens to identify itself as `7.x-rc6`, `7.x`, or `7.x-123-gabcdef` is secondary.

That also removes a surprising amount of policy complexity. There is no need to decide things like “RC kernels belong in testing” or “Mesa releases belong in stable.” The actual question is simply:

> **Does this complete OS snapshot work?**

A late kernel RC can easily be less risky than an early final release combined with a new Mesa or systemd regression. Integration testing is a better signal than individual upstream version labels.

### The release model can therefore be extremely small

```text
                 UPSTREAM HEADS
                       │
                       ▼
              Integration attempt
                       │
              ┌────────┴────────┐
              │                 │
             FAIL              PASS
              │                 │
           logs only            ▼
                         GREEN SNAPSHOT
                               │
                   ┌───────────┼───────────┐
                   │           │           │
              latest-green    edge       stable
                  immediately  after soak  after validation
```

`latest-green`, `edge`, and `stable` are all pointers to the **same class of immutable snapshot**.

They differ only in accumulated confidence.

For example:

```text
snapshot 184
Linux      7.4-rc7-213-g...
systemd    main @ abc123
Mesa       main @ def456
PipeWire   master @ 789abc
labwc      master @ 012def

Day 0:
latest-green → 184

Day 3:
edge         → 184

Day 14:
stable       → 184
```

Not a single byte changes.

Meanwhile:

```text
latest-green → 196
edge         → 191
stable       → 184
```

All three remain HEAD-derived systems.

## This also fits BuildStream particularly well

The BuildStream graph itself becomes the release definition.

A snapshot manifest could record:

```yaml
snapshot: 20261007.2134

freedesktop-sdk:
  ref: 924ee52...

overrides:
  systemd: 5138afe...
  linux: 81abc91...
  mesa: f5c213a...
  pipewire: a8139dc...
  wireplumber: 12eac31...
  labwc: ff491ce...

build:
  source_manifest: sha256:...
  build_graph: sha256:...
```

The important identity isn't:

```text
Linux 7.4-rc7
```

or:

```text
systemd 263-devel
```

It is:

```text
MyOS snapshot 20261007.2134
```

Everything underneath that is provenance.

That is conceptually much closer to firmware or an appliance OS than to a package distribution.

### It simplifies bug reporting too

Instead of:

> Mesa version? Kernel version? systemd version? Which packages were upgraded?

the primary debugging identifier becomes:

```text
IMAGE_VERSION=20261007.2134
```

That uniquely determines the entire graph.

Then:

```text
manifest(20261007.2134)
```

reveals every source commit.

That is a very strong property.

## HEAD should mean designated upstream HEAD

One slight refinement: not necessarily literally the repository's default branch for absolutely everything.

The project should define a **tracking branch** for each component:

```text
Linux       torvalds/master
systemd     main
Mesa        main
PipeWire    master
WirePlumber master
labwc       master
FDSDK       master
```

That distinction matters for projects with maintenance or staging branches.

The rule becomes:

> Track the designated upstream development branch unless an explicit temporary exception exists.

Not:

> Guess which branch looks newest.

## Temporary pins become exceptions to the model

A broken HEAD should normally stop publication:

```text
new HEAD set
   ↓
build fails
   ↓
latest-green stays where it is
```

That is preferable to silently carrying old components forward.

But occasionally something may remain broken upstream long enough that a temporary pin is useful.

Make that explicit:

```yaml
mesa:
  desired: main@abc123
  selected: main@891def
  exception: true
  reason: "Regression #412"
```

Then the project can expose something like:

```text
HEAD conformity: 8 / 9
```

A pin is therefore visible technical debt rather than an invisible distro patch policy.

## Promotion becomes the entire notion of stability

That gives a nice definition:

**Green** means the snapshot passes mandatory automated integration.

**Edge** means the exact green snapshot has survived additional automated and physical-hardware testing.

**Stable** means the exact same snapshot has accumulated enough field evidence to be recommended broadly.

No separate stable source branch.

No backport queue.

No rebuilding.

No “stable package versions.”

And unless the project eventually acquires a very different user base, there may never be a reason to create a traditional maintenance branch at all.

### Stable can still move quickly

Promotion doesn't need to mean weeks.

For example:

```text
latest-green:
    every successful integration

edge:
    12–48 hours + selected hardware tests

stable:
    3–7 days + no blocker reports
```

The exact windows can evolve.

A really good snapshot could move:

```text
green → edge → stable
```

quite quickly.

A questionable one may never leave `latest-green`.

The important thing is that **time alone doesn't promote anything**. Test evidence does.

## This also makes the Hardware/Virt split more elegant

One snapshot represents both:

```text
snapshot 184
│
├── virt-aarch64
├── virt-x86_64
├── hardware-aarch64
├── hardware-x86_64
├── desktop-aarch64
├── desktop-x86_64
└── admin extensions
```

All of those come from the same source graph.

Promotion should therefore be snapshot-wide.

For example, if:

```text
Virt x86-64       PASS
Virt aarch64      PASS
Hardware x86-64   PASS
Hardware aarch64  FAIL
```

then perhaps the snapshot is not eligible for `edge`.

That prevents different profiles from quietly becoming different distributions.

You could still publish partial green snapshots during early development, but once Edge/Stable exist, I'd make their gates require the supported matrix.

## There is a deeper philosophical advantage

Traditional package distributions ask:

```text
Is package X stable?
Is package Y stable?
Can X 1.4 coexist with Y 2.1?
```

This OS asks:

```text
Does artifact S work?
```

The unit of validation changes from:

```text
package
```

to:

```text
whole-system snapshot
```

That matches immutable image delivery much better.

It also fits the original desire to run very new software because the project's confidence comes from **testing the assembled artifact**, not from waiting for arbitrary upstream labels to change from `-rc` to final.

So I would now make this an explicit architectural principle:

> **Upstream version labels do not define release maturity. The complete immutable system image is the unit of integration, testing, promotion, rollback, and support.**

That one sentence ties together the HEAD-tracking policy, BuildStream graph, immutable images, promotion-based Stable, and the decision not to maintain a conventional package repository.

FDSDK itself fits the same model, but at a **different layer**. The clean approach is:

> **Track FDSDK `master` as one of the upstream HEADs, pin its exact commit into each integration snapshot, and treat FDSDK’s own bootstrap/toolchain graph as part of that snapshot’s provenance.**

The important distinction is between **the build bootstrap used to execute BuildStream** and **the FDSDK bootstrap/toolchain being built inside BuildStream**.

### Think of four layers

```text
Layer 0 — runner bootstrap
──────────────────────────
Linux VM / GitHub runner
Python
BuildStream
buildbox / bubblewrap
Git
CA certificates

          │
          ▼

Layer 1 — FDSDK bootstrap
──────────────────────────
FDSDK master @ exact SHA
bootstrap compiler
bootstrap libc
binutils
final compiler/toolchain
runtime foundations

          │
          ▼

Layer 2 — MyOS integration graph
─────────────────────────────────
FDSDK components
+ systemd HEAD override
+ Linux HEAD
+ Mesa HEAD override
+ PipeWire HEAD override
+ labwc HEAD
+ project configuration

          │
          ▼

Layer 3 — deployable artifact
──────────────────────────────
MyOS snapshot N
root image
UKI
sysexts
manifest
```

FDSDK already maintains an explicit `elements/bootstrap/` graph and can build/check out its bootstrap with `make bootstrap`; BuildStream itself is designed to build complete toolchains and bootable systems from a sandbox-controlled dependency graph. [GitLab](https://gitlab.com/freedesktop-sdk/freedesktop-sdk/-/tree/master/elements?utm_source=chatgpt.com)

## FDSDK `master` becomes another HEAD input

The integration resolver could record:

```yaml
snapshot: 20261007.2330

framework:
  freedesktop-sdk:
    branch: master
    commit: 7a3daa63...

tracked:
  systemd:
    branch: main
    commit: ...
  linux:
    branch: master
    commit: ...
  mesa:
    branch: main
    commit: ...
  pipewire:
    branch: master
    commit: ...
```

Then:

```text
FDSDK master moved?
       │
       ▼
new integration candidate

systemd moved?
       │
       ▼
new integration candidate

Linux moved?
       │
       ▼
new integration candidate
```

There is no concept of:

> FDSDK 26.08 is stable, therefore Stable must stay on 26.08.

A snapshot promoted to Stable might have been built from some arbitrary FDSDK-master commit between formal FDSDK releases.

FDSDK's formal releases become interesting upstream milestones, but not MyOS release boundaries.

That fits the whole-system philosophy much better.

---

## But don't track every package inside FDSDK independently

This is an important boundary.

FDSDK already supplies an integrated universe containing hundreds of components. Its stated purpose includes integration and validation of a shared dependency platform, and `master` is actively updated component-by-component. [GitLab](https://gitlab.com/freedesktop-sdk/freedesktop-sdk/-/tree/master?utm_source=chatgpt.com)

So MyOS should consume:

```text
FDSDK master
```

as a coherent baseline.

Then explicitly override only **components that matter to the project's identity**:

```text
FDSDK master
    │
    ├── glibc             use FDSDK selection
    ├── GCC               use FDSDK selection
    ├── binutils          use FDSDK selection
    ├── libxml2           use FDSDK selection
    ├── compression libs  use FDSDK selection
    ├── hundreds more     use FDSDK selection
    │
    ├── systemd ───────── OVERRIDE → upstream main
    ├── Mesa ──────────── OVERRIDE → upstream main
    ├── PipeWire ──────── OVERRIDE → upstream master
    │
    └── Linux             probably project-owned entirely
```

Otherwise the project silently becomes responsible for tracking thousands of upstream projects.

The philosophy would therefore be:

> **FDSDK HEAD defines the continuously integrated foundation; selected strategic components are promoted out of that foundation and tracked directly at upstream HEAD.**

That's a manageable definition.

---

# FDSDK changes should trigger integration like anything else

Suppose nothing interesting changes upstream except FDSDK:

```text
FDSDK:
    abc123 → def456

systemd:
    unchanged

Linux:
    unchanged

Mesa:
    unchanged
```

Still run an integration.

FDSDK may have changed:

- glibc;
- GCC;
- LLVM;
- libdrm;
- PAM;
- cryptsetup;
- BuildStream recipes;
- compiler flags;
- dependency topology.

Those can absolutely change the resulting OS even if project-owned HEAD overrides remain fixed.

So:

```text
FDSDK master update
        ↓
resolve new SHA
        ↓
BuildStream evaluates graph
        ↓
reuse unaffected cached elements
        ↓
rebuild affected closure
        ↓
build MyOS images
        ↓
integration test
        ↓
green snapshot
```

That makes FDSDK itself part of the tested integrated object.

---

## A broken FDSDK master simply stops snapshots

Exactly the same rule should apply.

Suppose:

```text
FDSDK master @ B
        +
systemd HEAD
        +
Linux HEAD
        ↓
FAIL
```

Then:

```text
latest-green → previous snapshot
```

No new image gets published.

The project should **not automatically fall back to the previous FDSDK commit** and pretend everything remains HEAD.

If the breakage lasts long enough, an explicit temporary exception can pin FDSDK:

```yaml
freedesktop-sdk:
  desired: master@abcdef
  selected: master@123456
  exception: true
  reason: "Bootstrap regression upstream"
```

Same policy as Mesa/systemd/etc.

This gives a single concept of upstream conformity.

Perhaps:

```text
HEAD status
──────────────────
FDSDK       ✓
systemd     ✓
Linux       ✓
Mesa        ✓
PipeWire    ✓
labwc       ✓

6 / 6 at designated HEAD
```

or:

```text
FDSDK       PINNED - 4 commits behind
systemd     ✓
Linux       ✓
Mesa        ✓
PipeWire    ✓
labwc       ✓

5 / 6 at designated HEAD
```

---

# The really interesting question is the bootstrap compiler

There is a potential conceptual rabbit hole:

> If FDSDK builds the compiler that builds the OS, what builds that compiler?

FDSDK already has an explicit bootstrap graph for exactly this purpose. Its current tree retains `elements/bootstrap/`, and ongoing FDSDK work is actually reducing accidental runtime leakage from the bootstrap environment into derived systems; `bootstrap/bootstrap.bst` remains the cross-compilation/bootstrap stack. [GitLab](https://gitlab.com/freedesktop-sdk/freedesktop-sdk/-/tree/master/elements?utm_source=chatgpt.com)

Conceptually:

```text
external bootstrap seed
       │
       ▼
bootstrap compiler
       │
       ▼
bootstrap libc/binutils
       │
       ▼
final FDSDK compiler
       │
       ▼
final FDSDK runtime
       │
       ▼
MyOS
```

That bootstrap chain should remain FDSDK's responsibility.

I would **not fork the FDSDK bootstrap initially**.

Doing so turns the project from:

> experimental OS integration project

into:

> experimental OS + toolchain bootstrap distribution.

That adds tremendous maintenance without improving the core experiment.

---

# Layer 0 should be boring

The host-side tools deserve almost the opposite policy.

Do **not** track HEAD for:

```text
BuildStream itself
buildbox
Python used to run BuildStream
Lima/Tart builder image
GitHub Actions runner bootstrap
```

at least initially.

Those aren't part of the OS experiment.

Pin them reasonably tightly:

```text
builder environment:

BuildStream = known-good 2.x
buildbox    = known-good version
Python      = known-good release
```

The job of Layer 0 is simply:

> reliably execute the hermetic BuildStream graph.

BuildStream's sandbox is explicitly designed so build dependencies and filesystem state are supplied by the graph rather than inherited from the host. On Linux its normal sandbox backend uses buildbox/bubblewrap and namespaces for this isolation. [BuildStream Documentation](https://docs.buildstream.build/2.6/arch_sandboxing.html?utm_source=chatgpt.com)

So ideally:

```text
Ubuntu runner
Fedora runner
local Lima VM
```

all produce identical target artifacts because none of their toolchains are used to compile MyOS.

---

## Pin the runner as an OCI image eventually

A nice progression would be:

```text
bootstrap/runner/
    Containerfile
```

producing something like:

```text
ghcr.io/project/myos-builder:1
```

containing only:

```text
BuildStream
buildbox
bubblewrap
Git
SSH
CA certificates
basic host utilities
```

Then local Linux VM:

```text
myos-builder VM
        │
        ▼
myos-builder container
        │
        ▼
bst build
```

and GitHub:

```text
GitHub Linux runner
        │
        ▼
same builder environment
        │
        ▼
bst build
```

The container itself could be infrequently refreshed.

However, BuildStream's sandboxing requirements mean blindly putting everything inside arbitrary Docker layers can be awkward; the important part is versioning the **bootstrap recipe/environment**, not necessarily forcing container nesting everywhere.

---

# The bootstrap environment should get its own identity

Each MyOS snapshot should ideally record both:

```text
source graph
```

and:

```text
build orchestrator
```

For example:

```json
{
  "snapshot": "20261007.2330",

  "bootstrap": {
    "buildstream": "2.8.1",
    "buildbox": "...",
    "builder_image": "sha256:..."
  },

  "sources": {
    "freedesktop-sdk": "7a3daa63...",
    "systemd": "...",
    "linux": "...",
    "mesa": "..."
  }
}
```

The bootstrap environment isn't necessarily part of the **semantic identity** of the OS, but it absolutely belongs in provenance.

Then reproducibility testing can eventually ask:

```text
same source manifest
+ different clean runner
       │
       ▼
same artifact hashes?
```

That's a valuable CI test.

---

# There are actually two FDSDK policies

This distinction is useful.

### FDSDK graph policy

```text
track: master
```

Aggressive.

This determines what goes into the OS.

### Build tooling policy

```text
BuildStream:
    pinned known-good

buildbox:
    pinned known-good
```

Conservative.

This determines how the graph is evaluated.

Keeping those separate means a BuildStream regression doesn't get conflated with a systemd/kernel/Mesa integration regression.

---

# FDSDK's own component updates are inherited automatically

Suppose FDSDK master changes:

```text
glibc 2.xx → 2.xy
```

Then the next integration gets it automatically.

No MyOS PR for glibc is necessary.

Similarly:

```text
libpng
libjpeg
fontconfig
freetype
OpenSSL
libarchive
...
```

flow naturally through FDSDK master.

This dramatically reduces the project's update machinery.

The update watcher only needs to explicitly track:

```text
FDSDK master
systemd main
Linux master
Mesa main
PipeWire master
WirePlumber master
labwc master
possibly wlroots
```

instead of thousands of repositories.

That is perhaps the most important reason to retain FDSDK.

---

## It makes the source graph hierarchical

Rather than:

```text
MyOS
├── glibc HEAD
├── GCC HEAD
├── binutils HEAD
├── zlib HEAD
├── libpng HEAD
├── OpenSSL HEAD
├── ...
├── 900 more upstreams
├── systemd HEAD
├── Linux HEAD
└── Mesa HEAD
```

use:

```text
MyOS
│
├── FDSDK master
│   ├── glibc
│   ├── GCC
│   ├── LLVM
│   ├── binutils
│   ├── OpenSSL
│   ├── libdrm
│   ├── hundreds more
│   └── their integration policy
│
├── override: systemd HEAD
├── override: Mesa HEAD
├── override: PipeWire HEAD
│
├── owned: Linux HEAD
├── owned: labwc HEAD
└── owned: MyOS configuration
```

FDSDK is effectively a **continuously updated dependency supercomponent**.

That is a useful abstraction.

---

# Promotion still works identically

Suppose:

```text
snapshot 512

FDSDK master  = aaa111
systemd HEAD  = bbb222
Linux HEAD    = ccc333
Mesa HEAD     = ddd444
```

After CI:

```text
latest-green → 512
```

Then:

```text
edge → 512
```

and eventually:

```text
stable → 512
```

FDSDK does not get upgraded during promotion.

Even if FDSDK master has moved 150 commits by the time snapshot 512 reaches Stable:

```text
FDSDK current master = zzz999

Stable snapshot 512:
    still aaa111
```

That is precisely what treating the whole image as an integrated object means.

---

# A newer FDSDK does not invalidate Stable

This is worth making explicit.

There is no:

```text
FDSDK released 27.08
    ↓
MyOS stable is obsolete
```

relationship.

Instead:

```text
new FDSDK commit
      ↓
candidate source graph
      ↓
integration
      ↓
new snapshot 540
```

Whether 540 gets promoted is entirely independent.

The stable snapshot remains valid because it is a closed, reproducible graph.

---

## Formal FDSDK releases become checkpoints

FDSDK tags such as 26.08 are still useful.

FDSDK 26.08 introduced meaningful structural changes such as making `runtime-minimal.bst` omit Bash/Coreutils, specifically allowing downstreams to replace the bootstrap userland more freely. [GitLab](https://gitlab.com/freedesktop-sdk/freedesktop-sdk/-/tags/freedesktop-sdk-26.08.0?utm_source=chatgpt.com)

So when master passes a formal release tag:

```text
FDSDK master
      │
      ├── commits
      ├── commits
      ├── 27.08 tag
      ├── commits
      └── commits
```

the corresponding MyOS snapshot could get metadata:

```text
FDSDK milestone: 27.08
```

and perhaps be retained as a checkpoint.

But nothing special needs to happen technically.

---

# Eventually, self-hosting could be an interesting milestone

A much later experiment would be:

```text
MyOS development environment
        │
        ▼
BuildStream
        │
        ▼
FDSDK bootstrap
        │
        ▼
build MyOS itself
```

In other words, demonstrate that:

```text
MyOS N
   builds
MyOS N+1
```

But this should be considered a **reproducibility/self-hosting test**, not a requirement for the architecture.

The Apple Silicon Linux builder VM can remain the official bootstrap environment indefinitely.

What matters is that the actual compilers and libraries used for target construction come from the BuildStream/FDSDK graph, rather than accidentally leaking from Ubuntu/Fedora/macOS.

---

# So the dependency hierarchy becomes very clean

```text
        BORING BOOTSTRAP
────────────────────────────────
 BuildStream + buildbox
 pinned runner environment
 Linux VM / GitHub runner
────────────────────────────────
               │
               ▼
         TRACKED FDSDK HEAD
────────────────────────────────
 compiler bootstrap
 libc
 toolchain
 generic dependency universe
 common recipes
────────────────────────────────
               │
               ▼
       TRACKED MYOS HEAD SET
────────────────────────────────
 systemd HEAD
 Linux HEAD
 Mesa HEAD
 PipeWire HEAD
 labwc HEAD
 MyOS configuration
────────────────────────────────
               │
               ▼
       INTEGRATED OS SNAPSHOT
────────────────────────────────
 Hardware
 Virt
 desktop sysext
 admin sysext
 UKIs
 root images
────────────────────────────────
               │
               ▼
 latest-green → edge → stable
```

That is the division I would choose.

**FDSDK `master` belongs inside the aggressively moving source graph. BuildStream/buildbox and the runner environment belong outside it and should remain deliberately boring.**

That preserves the project's HEAD-tracking philosophy without destabilizing the machinery required to determine whether HEAD actually works.


