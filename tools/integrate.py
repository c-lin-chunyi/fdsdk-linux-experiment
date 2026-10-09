#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Integration cycles (docs/spec.md §17, §31).

  resolve [--force | --frozen]               pin every tracked component to an exact commit
  record --result green|failed|aborted [--no-commit]
                                             publish the snapshot or record the failure

`resolve` reads policy/tracking.toml and writes the resolved refs into project.refs and
junction.refs (and, for Linux, the selected commit into include/kernel/linux-commit.yml). It
also writes the snapshot id to include/snapshot.yml and starts a manifest in
out/integrations/<id>/. It exits 3 when nothing changed since the snapshot `latest` names.

`record --result green` publishes out/snapshots/<id>/ (manifest, compressed image,
SHA256SUMS) and moves the `latest` pointer (out/snapshots/latest.json) to it. It then
commits the refs and tags the commit `snapshot-<id>` (§17.4), unless the tree has
uncommitted changes outside the refs files, so tags always match real history. The resolved
refs stay in the working tree: it always holds the pins of `latest`. `record --result
failed` keeps the manifest and serial log, and restores the files resolve changed.

`resolve --frozen` keeps every tracked component at the commit the snapshot `latest`
recorded, without asking upstream: a development cycle that tests a structural change on a
source set the cache already holds (docs/decisions.md D49). Its manifest says so
(`mode: frozen`, `frozen_from`), and a green frozen cycle is a snapshot like any other. The
next unfrozen cycle moves everything to HEAD on its own, so an upstream regression is never
mixed into a structural step.

`record --result aborted` closes an interrupted cycle: like `failed`, it restores the refs
and publishes nothing, but it makes no claim about the inputs.

An override whose FDSDK original changed fails the cycle at resolve (§31.4).

Both results record the SELinux state and the AVC denials seen on the serial console
(docs/security.md §15: Stage 0 records them without gating on them).

Runs in the builder: needs bst, git, zstd and ruamel.yaml.
"""

import argparse
import datetime
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import tomllib
import struct
import urllib.request
import zlib

from ruamel.yaml import YAML

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY = os.path.join(REPO, "policy", "tracking.toml")
SNAPSHOT_YML = os.path.join(REPO, "include", "snapshot.yml")
OUT = os.path.join(REPO, "out")
INTEGRATIONS = os.path.join(OUT, "integrations")
SNAPSHOTS = os.path.join(OUT, "snapshots")
CHANNELS = os.path.join(OUT, "channels")
# Snapshots whose update artifacts are kept: `latest` and its predecessor.
KEEP_UPDATE_ARTIFACTS = 2
CURRENT = os.path.join(INTEGRATIONS, "current")
LATEST = os.path.join(SNAPSHOTS, "latest.json")
MIRRORS = os.path.expanduser("~/.cache/beamline/mirrors")
PROJECT = "beamline"

# Files resolve may change; restored on failure. All but snapshot.yml are committed on green.
STATEFUL = ["project.refs", "junction.refs", "include/kernel/linux-commit.yml", "include/snapshot.yml"]
SELECTION_FILES = [f for f in STATEFUL if f != "include/snapshot.yml"]

DESCRIBE = re.compile(r"^(?P<tag>.+)-(?P<distance>\d+)-g(?P<sha>[0-9a-f]{40})$")
SHA = re.compile(r"^[0-9a-f]{40}$")
NO_CHANGE = 3
RESOLVE_FAILED = 4


def log(msg):
    print(f"integrate: {msg}", file=sys.stderr, flush=True)


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, text=True, capture_output=True, **kw).stdout.strip()


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


# Refs files ---------------------------------------------------------------------------

def yaml():
    y = YAML()
    y.preserve_quotes = True
    y.indent(mapping=2, sequence=2, offset=0)   # the layout BuildStream writes
    y.width = 4096                                # never fold long refs
    return y


def read_ref(refs_file, element):
    with open(os.path.join(REPO, refs_file), encoding="utf-8") as f:
        data = yaml().load(f) or {}
    entries = data.get("projects", {}).get(PROJECT, {}).get(element) or []
    return entries[0].get("ref") if entries else None


def write_ref(refs_file, element, ref):
    path = os.path.join(REPO, refs_file)
    y = yaml()
    with open(path, encoding="utf-8") as f:
        data = y.load(f) or {}
    elements = data.setdefault("projects", {}).setdefault(PROJECT, {})
    entries = elements.get(element) or [{}]
    entries[0] = {"ref": ref}          # the tracked git source is always the first source
    elements[element] = entries
    with open(path, "w", encoding="utf-8") as f:
        y.dump(data, f)


def commit_of(ref):
    m = DESCRIBE.match(ref)
    if m:
        return m.group("sha")
    if SHA.match(ref):
        return ref
    sys.exit(f"integrate: cannot read a commit from ref {ref!r}")


def nearest_tag(ref):
    m = DESCRIBE.match(ref)
    return f"{m.group('tag')}-{m.group('distance')}-g{m.group('sha')[:12]}" if m else None


# Upstream queries ---------------------------------------------------------------------

def ls_remote(url, branch):
    out = run(["git", "ls-remote", url, f"refs/heads/{branch}"])
    if not out:
        sys.exit(f"integrate: {url} has no branch {branch}")
    return out.split()[0]


def gitlab_ci_green(project, branch, api="https://gitlab.com"):
    url = (f"{api}/api/v4/projects/{project.replace('/', '%2F')}"
           f"/pipelines?ref={branch}&status=success&per_page=1")
    with urllib.request.urlopen(url, timeout=60) as resp:
        pipelines = json.load(resp)
    if not pipelines:
        sys.exit(f"integrate: no successful pipeline on {project} {branch}")
    return pipelines[0]["sha"]


def mirror(name, url, branch):
    """Treeless bare mirror, enough for `git describe` and commit counting."""
    path = os.path.join(MIRRORS, f"{name}.git")
    if not os.path.isdir(path):
        os.makedirs(MIRRORS, exist_ok=True)
        run(["git", "init", "--bare", "--quiet", path])
        run(["git", "-C", path, "remote", "add", "origin", url])
        run(["git", "-C", path, "config", "remote.origin.promisor", "true"])
        run(["git", "-C", path, "config", "remote.origin.partialclonefilter", "tree:0"])
    run(["git", "-C", path, "fetch", "--quiet", "--filter=tree:0", "--tags", "--force",
         "origin", f"+refs/heads/{branch}:refs/heads/{branch}"])
    return path


def github_nearest_tag(repo, sha):
    """Best-effort git-describe for an archive-selected commit, without a clone: the release
    named by the commit's top-level Makefile, and the commit's distance from it."""
    try:
        with urllib.request.urlopen(f"https://raw.githubusercontent.com/{repo}/{sha}/Makefile",
                                    timeout=60) as resp:
            head = resp.read(4096).decode()
        v = dict(re.findall(r"^(VERSION|PATCHLEVEL|SUBLEVEL|EXTRAVERSION) = ?(.*)$", head, re.M))
        tag = f"v{v['VERSION']}.{v['PATCHLEVEL']}"
        tag += (f".{v['SUBLEVEL']}" if v.get("SUBLEVEL", "0") != "0" else "") + v.get("EXTRAVERSION", "")
        with urllib.request.urlopen(f"https://api.github.com/repos/{repo}/compare/{tag}...{sha}",
                                    timeout=60) as resp:
            ahead = json.load(resp)["ahead_by"]
        return f"{tag}-{ahead}-g{sha[:12]}"
    except (OSError, KeyError, ValueError) as exc:
        log(f"warning: no nearest tag for {repo} {sha[:12]}: {exc}")
        return None


def describe(path, sha):
    return run(["git", "-C", path, "describe", "--tags", "--long", "--abbrev=40", sha])


def lag(path, selected, head):
    return int(run(["git", "-C", path, "rev-list", "--count", f"{selected}..{head}"]))


# Resolve ------------------------------------------------------------------------------

def bst_track(arch, elements):
    if elements:
        subprocess.run(["bst", "--no-colors", "--option", "arch", arch, "source", "track",
                        "--deps", "none", *elements], cwd=REPO, check=True)


def write_variable(rel, variable, value):
    """Set `variable` in a variables-only include written by integration cycles."""
    path = os.path.join(REPO, rel)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    text, count = re.subn(rf"^  {re.escape(variable)}: .*$", f"  {variable}: {value}", text, flags=re.M)
    if count != 1:
        sys.exit(f"integrate: {rel} has no `{variable}:` to set")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read_variable(rel, variable):
    with open(os.path.join(REPO, rel), encoding="utf-8") as f:
        m = re.search(rf"^  {re.escape(variable)}: (.*)$", f.read(), flags=re.M)
    if not m:
        sys.exit(f"integrate: {rel} has no `{variable}:`")
    return m.group(1).strip()


def resolve_archive(name, comp, arch):
    """github-archive: the branch HEAD from `url` (the authority for the commit), built from
    GitHub's archive of that commit. A git fetch of a repository as large as linux.git is slow
    and needs a mirror hosted runners do not keep (docs/decisions.md D32)."""
    url, branch, repo = comp["url"], comp["branch"], comp["github"]
    head = ls_remote(url, branch)
    github_head = ls_remote(f"https://github.com/{repo}.git", branch)
    entry = {"tracking": branch, "head_at_resolution": head, "lag_commits": 0,
             "archive": f"github.com/{repo}"}
    if github_head != head:
        entry["github_head_at_resolution"] = github_head
        log(f"warning: {name}: github.com/{repo} {branch} is at {github_head[:12]}, "
            f"{url} at {head[:12]}")
    pin = comp.get("pin")
    if pin:
        sha = pin["ref"]
        entry.update(status="PINNED", lag_commits=None,
                     pin={k: pin[k] for k in ("reason", "issue") if k in pin})
    else:
        sha = head
        entry["status"] = "HEAD"
    write_variable(comp["commit_file"], comp["commit_variable"], sha)

    bst_track(arch, comp["elements"])
    refs_seen = {read_ref(comp["refs"], e) for e in comp["elements"]}
    if len(refs_seen) != 1:
        sys.exit(f"integrate: {name}: elements resolved to different refs {refs_seen}")
    entry.update(selected_ref=sha, commit=sha, nearest_tag=github_nearest_tag(repo, sha),
                 source=f"https://github.com/{repo}/archive/{sha}.tar.gz",
                 archive_sha256=refs_seen.pop())
    return entry


def resolve_component(name, comp, arch):
    if comp.get("select") == "github-archive":
        return resolve_archive(name, comp, arch)
    url, branch, elements, refs = comp["url"], comp["branch"], comp["elements"], comp["refs"]
    head = ls_remote(url, branch)
    entry = {"tracking": branch, "head_at_resolution": head, "lag_commits": None}
    pin = comp.get("pin")
    select = comp.get("select", "head")

    if pin:
        ref = pin["ref"]
        entry.update(status="PINNED", pin={k: pin[k] for k in ("reason", "issue") if k in pin})
        for element in elements:
            write_ref(refs, element, ref)
        if select == "gitlab-ci-green" or comp.get("mirror"):
            entry["lag_commits"] = lag(mirror(name, url, branch), commit_of(ref), head)
    elif select == "gitlab-ci-green":
        sha = gitlab_ci_green(comp["gitlab_project"], branch, comp.get("gitlab_api", "https://gitlab.com"))
        path = mirror(name, url, branch)
        ref = describe(path, sha)
        for element in elements:
            write_ref(refs, element, ref)
        entry.update(status="HEAD", lag_commits=lag(path, sha, head), selection="newest upstream CI-green commit")
        entry["mirror"] = path
    else:
        for attempt in (1, 2):
            bst_track(arch, elements)
            refs_seen = {read_ref(refs, e) for e in elements}
            if len(refs_seen) != 1:
                sys.exit(f"integrate: {name}: elements resolved to different refs {refs_seen}")
            ref = refs_seen.pop()
            if commit_of(ref) == head:
                break
            head = ls_remote(url, branch)      # upstream moved meanwhile: track again once
            entry["head_at_resolution"] = head
        else:
            sys.exit(f"integrate: {name}: tracked {ref}, but {branch} is at {head}. Does the "
                     f"element's `track:` follow the policy branch?")
        entry.update(status="HEAD", lag_commits=0)

    entry.update(selected_ref=ref, commit=commit_of(ref), nearest_tag=nearest_tag(ref))
    return entry


OVERRIDES = os.path.join(REPO, "elements", "overrides")
COPIED_FROM = re.compile(r"^# Copied from: (?P<project>freedesktop-sdk|gnome-build-meta) (?P<sha>[0-9a-f]{40})\n"
                         r"#\s+(?P<path>\S+)", re.M)


def override_drift(upstreams):
    """Overrides are copies of FDSDK or gnome-build-meta recipes (decisions D15, D29). Report
    each one whose original changed between the recorded commit and the selected one
    (§31.4). `upstreams` maps a project name to its resolved source entry."""
    if not os.path.isdir(OVERRIDES):
        return []
    warnings = []
    for name in sorted(os.listdir(OVERRIDES)):
        with open(os.path.join(OVERRIDES, name), encoding="utf-8") as f:
            m = COPIED_FROM.search(f.read())
        upstream = upstreams.get(m.group("project")) if m else None
        if not upstream or not upstream.get("mirror") or m.group("sha") == upstream["commit"]:
            continue
        diff = subprocess.run(["git", "-C", upstream["mirror"], "diff", "--quiet", m.group("sha"),
                               upstream["commit"], "--", m.group("path")])
        if diff.returncode == 1:
            warnings.append(f"overrides/{name}: {m.group('project')} changed {m.group('path')} since "
                            f"{m.group('sha')[:12]}; re-copy it from {upstream['commit'][:12]}")
    return warnings


FDSDK_JUNCTION = os.path.join(REPO, "elements", "junctions", "freedesktop-sdk.bst")
GBM_PREFIX = "junctions/gnome-build-meta.bst:"
# gnome-build-meta's FDSDK overrides that Beamline does not carry (decisions D28): its
# systemd family (Beamline's own) and its kernel module certificate.
GBM_NOT_CARRIED = {
    "components/_private/systemd-base.bst", "components/systemd.bst",
    "components/systemd-ukify.bst", "components/systemd-libs.bst",
    "components/linux-module-cert.bst",
}
OVERRIDE_LINE = re.compile(r"^\s+(components/\S+\.bst):\s*(\S+\.bst)\s*$", re.M)


def gbm_override_drift(gbm):
    """Beamline's FDSDK junction carries gnome-build-meta's FDSDK overrides (decisions
    D28). Report every difference from gbm's list at the selected commit (§31.4)."""
    theirs_text = run(["git", "-C", gbm["mirror"], "show", f"{gbm['commit']}:elements/freedesktop-sdk.bst"])
    section = theirs_text[theirs_text.index("overrides:"):]
    theirs = {k: v for k, v in OVERRIDE_LINE.findall(section) if k not in GBM_NOT_CARRIED}
    with open(FDSDK_JUNCTION, encoding="utf-8") as f:
        ours_text = f.read()
    block = ours_text[ours_text.index("# BEGIN gnome-build-meta overrides"):
                      ours_text.index("# END gnome-build-meta overrides")]
    ours = {k: v[len(GBM_PREFIX):] for k, v in OVERRIDE_LINE.findall(block) if v.startswith(GBM_PREFIX)}
    problems = []
    for key in sorted(set(theirs) | set(ours)):
        if theirs.get(key) != ours.get(key):
            problems.append(f"gnome-build-meta overrides {key} with {theirs.get(key) or 'nothing'}; "
                            f"Beamline's FDSDK junction carries {ours.get(key) or 'nothing'}")
    return problems


def repository_state():
    """Repository commit plus a fingerprint of uncommitted changes (refs files excluded),
    so that "nothing changed" also works on a work-in-progress tree."""
    commit = run(["git", "-C", REPO, "rev-parse", "HEAD"])
    status = subprocess.run(["git", "-C", REPO, "status", "--porcelain", "--untracked-files=all"],
                            check=True, text=True, capture_output=True).stdout
    changed = sorted(line[3:] for line in status.splitlines() if line[3:] not in STATEFUL)
    fingerprint = hashlib.sha256()
    for rel in changed:
        fingerprint.update(rel.encode() + b"\0")
        path = os.path.join(REPO, rel)
        if os.path.isfile(path):
            with open(path, "rb") as f:
                fingerprint.update(f.read())
    return {"commit": commit, "dirty": bool(changed), "changed_files": changed,
            "uncommitted_sha256": fingerprint.hexdigest() if changed else None}


def provenance():
    def quiet(cmd):
        try:
            return run(cmd).splitlines()[0]
        except (OSError, subprocess.CalledProcessError, IndexError):
            return None
    osrel = {}
    if os.path.exists("/etc/os-release"):
        for line in open("/etc/os-release", encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            osrel[k] = v.strip('"')
    return {
        "buildstream": quiet(["bst", "--version"]),
        "buildbox": quiet(["buildbox-casd", "--version"]),
        "builder": osrel.get("PRETTY_NAME"),
        "kernel": platform.release(),
    }


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def latest():
    if not os.path.exists(LATEST):
        return None
    return load_json(os.path.join(SNAPSHOTS, load_json(LATEST)["snapshot"], "manifest.json"))


def write_snapshot_id(value):
    with open(SNAPSHOT_YML, encoding="utf-8") as f:
        text = f.read()
    with open(SNAPSHOT_YML, "w", encoding="utf-8") as f:
        f.write(re.sub(r"^snapshot-id: .*$", f"snapshot-id: {value}", text, flags=re.M))


def backup_dir(snapshot):
    return os.path.join(INTEGRATIONS, snapshot, "before")


def restore(snapshot):
    for rel in STATEFUL:
        src = os.path.join(backup_dir(snapshot), rel)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(REPO, rel))


def cmd_resolve(args):
    if os.path.exists(CURRENT):
        sys.exit(f"integrate: integration {open(CURRENT).read().strip()} is still open; "
                 f"run `record` first")
    with open(POLICY, "rb") as f:
        policy = tomllib.load(f)

    # Ids have minute resolution (§17.2); a second cycle within the same minute waits.
    while True:
        now = utcnow()
        snapshot = now.strftime("%Y%m%d.%H%M")
        workdir = os.path.join(INTEGRATIONS, snapshot)
        if not (os.path.exists(workdir) or os.path.exists(os.path.join(SNAPSHOTS, snapshot))):
            break
        log(f"{snapshot} is taken; waiting for the next minute")
        time.sleep(61 - now.second)
    for rel in STATEFUL:
        dest = os.path.join(backup_dir(snapshot), rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(os.path.join(REPO, rel), dest)
    with open(CURRENT, "w") as f:
        f.write(snapshot + "\n")

    try:
        previous = latest()
        if args.frozen:
            sources = frozen_sources(policy, previous)
            drift = []
        else:
            sources = {}
            for name, comp in policy["component"].items():
                log(f"resolving {name} ({comp['branch']})")
                sources[name] = resolve_component(name, comp, args.arch)
            gbm = sources.get("gnome-build-meta", {})
            drift = override_drift({"freedesktop-sdk": sources.get("freedesktop-sdk", {}),
                                    "gnome-build-meta": gbm})
            if gbm.get("mirror"):
                drift += gbm_override_drift(gbm)
            for src in sources.values():
                src.pop("mirror", None)
        repo = repository_state()
        same_repo = previous and all(previous["repository"].get(k) == repo[k]
                                     for k in ("commit", "uncommitted_sha256"))
        same_sources = previous and {k: v["selected_ref"] for k, v in previous["sources"].items()} \
            == {k: v["selected_ref"] for k, v in sources.items()}
        if same_repo and same_sources and not (args.force or args.frozen):
            restore(snapshot)
            shutil.rmtree(workdir)
            os.remove(CURRENT)
            log(f"no change since snapshot {previous['snapshot']}")
            return NO_CHANGE

        at_head = sum(1 for v in sources.values() if v["status"] == "HEAD")
        manifest = {
            "snapshot": snapshot,
            "generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "result": "pending",
            "arch": [args.arch],
            "previous_green": previous["snapshot"] if previous else None,
            "repository": repo,
            "sources": sources,
            "head_conformity": f"{at_head}/{len(sources)}" if not args.frozen
                               else f"frozen at {previous.get('frozen_from', previous['snapshot'])}",
            "fixed": policy.get("fixed", {}),
            "override_drift": drift,
            "provenance": provenance(),
        }
        if args.frozen:
            manifest["mode"] = "frozen"
            manifest["frozen_from"] = previous.get("frozen_from", previous["snapshot"])
        if drift:
            manifest["result"] = "failed"
            manifest["failure"] = "override drift"
            write_json(os.path.join(workdir, "manifest.json"), manifest)
            restore(snapshot)
            os.remove(CURRENT)
            for line in drift:
                log(f"FAILED: {line}")
            log(f"integration {snapshot} FAILED at resolve; record: {workdir}")
            return RESOLVE_FAILED
        write_snapshot_id(snapshot)
        write_json(os.path.join(workdir, "manifest.json"), manifest)
    except BaseException:
        restore(snapshot)
        os.remove(CURRENT)
        raise

    log(f"snapshot candidate {snapshot}: HEAD conformity {manifest['head_conformity']}")
    for name, src in sources.items():
        pinned = f" {src['status']}" if src["status"] != "HEAD" else ""
        log(f"  {name:18} {src['selected_ref']}{pinned}")
    if repo["dirty"]:
        log(f"warning: uncommitted changes outside refs files: {', '.join(repo['changed_files'])}")
    return 0


def frozen_sources(policy, previous):
    """The source set of `latest`, unchanged: no upstream lookups, no tracking. `frozen_from`
    names the HEAD cycle that resolved it, through any frozen snapshots in between."""
    if not previous:
        sys.exit("integrate: --frozen needs a snapshot `latest` to freeze at")
    origin = previous.get("frozen_from", previous["snapshot"])
    sources = {}
    for name, comp in policy["component"].items():
        if name not in previous["sources"]:
            sys.exit(f"integrate: --frozen: {name} is not in snapshot {previous['snapshot']}; "
                     f"a new component needs an unfrozen cycle")
        src = dict(previous["sources"][name])
        if comp.get("select") == "github-archive":
            held = (read_variable(comp["commit_file"], comp["commit_variable"]),
                    {read_ref(comp["refs"], e) for e in comp["elements"]})
            want = (src["commit"], {src["archive_sha256"]})
        else:
            held = {read_ref(comp["refs"], e) for e in comp["elements"]}
            held = held.pop() if len(held) == 1 else held
            want = src["selected_ref"]
        if held != want:
            sys.exit(f"integrate: --frozen: {name} is at {held} in the tree, but snapshot "
                     f"{previous['snapshot']} has {want}; restore its refs first")
        src.update(status="FROZEN", frozen_from=origin)
        sources[name] = src
        log(f"frozen {name} at {src['selected_ref']}")
    return sources


# Record -------------------------------------------------------------------------------

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


AVC = re.compile(r"avc:\s+denied\s+\{ (?P<perms>[^}]+) \} for .*?"
                 r"scontext=(?P<scontext>\S+) tcontext=(?P<tcontext>\S+) tclass=(?P<tclass>\S+)")
AVC_COMM = re.compile(r"\bcomm=(\"[^\"]*\"|\S+)")
SELINUX_CONFIG = os.path.join(REPO, "files", "selinux", "config")


TEST_LOGS = ("serial.log", "serial-reboot.log", "serial-verity.log", "serial-boot-entries.log",
             "serial-update.log", "serial-run0.log", "serial-settings.log", "serial-admin.log",
             "serial-trust.log", "serial-desktop.log")
TEST_EVIDENCE = TEST_LOGS + ("desktop.ppm",)


def selinux_summary(serials):
    """SELinux state and the distinct AVC denials of the VM tests (security §15, §16)."""
    mode = None
    if os.path.exists(SELINUX_CONFIG):
        for line in open(SELINUX_CONFIG, encoding="utf-8"):
            if line.startswith("SELINUX="):
                mode = line.split("=", 1)[1].strip()
    denials, loaded = set(), False
    for serial in serials:
        if not os.path.exists(serial):
            continue
        for line in open(serial, encoding="utf-8", errors="replace"):
            loaded = loaded or "BEAMLINE_SELINUX_OK" in line
            m = AVC.search(line)
            if m:
                c = AVC_COMM.search(line)
                comm = c.group(1).strip('"') if c else ""
                denials.add(f"{{ {m.group('perms')} }} comm={comm} scontext={m.group('scontext')} "
                            f"tcontext={m.group('tcontext')} tclass={m.group('tclass')}")
    return {"policy_loaded": loaded, "mode": mode, "avc_denials": len(denials),
            "denials": sorted(denials)}


def ppm_to_png(src, dest):
    """The desktop screenshot as a PNG (QMP writes a binary PPM)."""
    with open(src, "rb") as f:
        _magic, size, _maxval, pixels = f.read().split(b"\n", 3)
    width, height = map(int, size.split())
    rows = b"".join(b"\x00" + pixels[y * width * 3:(y + 1) * width * 3] for y in range(height))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    with open(dest, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def keep_evidence(image_dir, dest, prefix=""):
    """Copy the VM tests' logs and screenshot (as PNG) into a snapshot or integration record."""
    for name in TEST_EVIDENCE:
        src = os.path.join(image_dir, name)
        if not os.path.exists(src):
            continue
        if name.endswith(".ppm"):
            ppm_to_png(src, os.path.join(dest, prefix + name[:-4] + ".png"))
        else:
            shutil.copyfile(src, os.path.join(dest, prefix + name))


def publish_update(image_dir, dest, snapshot):
    """Publish the snapshot's update artifacts (a signed channel directory, D52) and move the
    `latest` channel to them; promotion only ever relinks. Older snapshots keep their manifest,
    image and logs, but only the newest few keep their update artifacts."""
    update = os.path.join(image_dir, "update")
    if not os.path.isfile(os.path.join(update, "SHA256SUMS.gpg")):
        log("no update artifacts to publish")
        return
    shutil.copytree(update, os.path.join(dest, "update"))
    os.makedirs(CHANNELS, exist_ok=True)
    link = os.path.join(CHANNELS, "latest")
    tmp = link + ".new"
    if os.path.lexists(tmp):
        os.remove(tmp)
    os.symlink(os.path.join("..", "snapshots", snapshot, "update"), tmp)
    os.replace(tmp, link)
    log(f"channel latest -> snapshot {snapshot}")
    published = sorted(d for d in os.listdir(SNAPSHOTS)
                       if os.path.isdir(os.path.join(SNAPSHOTS, d, "update")))
    for old in published[:-KEEP_UPDATE_ARTIFACTS]:
        shutil.rmtree(os.path.join(SNAPSHOTS, old, "update"))
        log(f"pruned the update artifacts of snapshot {old}")


def changed_since(manifest, previous):
    if not previous:
        return list(manifest["sources"])
    old = {k: v["selected_ref"] for k, v in previous["sources"].items()}
    return [k for k, v in manifest["sources"].items() if old.get(k) != v["selected_ref"]]


def cmd_record(args):
    if not os.path.exists(CURRENT):
        sys.exit("integrate: no open integration; run `resolve` first")
    snapshot = open(CURRENT).read().strip()
    workdir = os.path.join(INTEGRATIONS, snapshot)
    manifest = load_json(os.path.join(workdir, "manifest.json"))
    previous = latest()
    image_dir = os.path.join(OUT, args.arch, "virt")

    manifest["selinux"] = selinux_summary([os.path.join(image_dir, name) for name in TEST_LOGS])
    if args.result in ("failed", "aborted"):
        manifest["result"] = args.result
        manifest["changed_since_green"] = changed_since(manifest, previous)
        keep_evidence(image_dir, workdir)
        write_json(os.path.join(workdir, "manifest.json"), manifest)
        restore(snapshot)
        os.remove(CURRENT)
        log(f"integration {snapshot} {args.result.upper()}; latest unchanged "
            f"({previous['snapshot'] if previous else 'none'})")
        log(f"inputs changed since latest: {', '.join(manifest['changed_since_green']) or 'none'}")
        log(f"record: {workdir}")
        return 0

    dest = os.path.join(SNAPSHOTS, snapshot)
    os.makedirs(dest)
    image = os.path.join(image_dir, "disk.raw")
    name = f"virt-{args.arch}.disk.raw"
    log(f"compressing {name}")
    subprocess.run(["zstd", "-q", "-T0", "-10", image, "-o", os.path.join(dest, name + ".zst")], check=True)
    keep_evidence(image_dir, dest, prefix=f"virt-{args.arch}.")

    manifest["result"] = "green"
    manifest["changed_since_green"] = changed_since(manifest, previous)
    manifest["artifacts"] = {name: {"sha256": sha256(image), "zst": name + ".zst",
                                    "zst_sha256": sha256(os.path.join(dest, name + ".zst"))}}
    write_snapshot_id("dev")
    manifest["git"] = record_in_git(snapshot, args.no_commit)
    write_json(os.path.join(dest, "manifest.json"), manifest)
    with open(os.path.join(dest, "SHA256SUMS"), "w") as f:
        for fname in sorted(os.listdir(dest)):
            if fname != "SHA256SUMS" and os.path.isfile(os.path.join(dest, fname)):
                f.write(f"{sha256(os.path.join(dest, fname))}  {fname}\n")
    publish_update(image_dir, dest, snapshot)
    write_json(LATEST, {"snapshot": snapshot})

    shutil.rmtree(workdir)
    os.remove(CURRENT)
    sel = manifest["selinux"]
    log(f"SELinux: policy {'loaded' if sel['policy_loaded'] else 'NOT loaded'}, {sel['mode']}, "
        f"{sel['avc_denials']} distinct AVC denials recorded")
    conformity = manifest["head_conformity"]
    log(f"snapshot {snapshot} GREEN: latest → {snapshot} "
        f"({conformity if manifest.get('mode') == 'frozen' else conformity + ' at HEAD'})")
    return 0


def record_in_git(snapshot, no_commit):
    """Commit the selection files and tag snapshot-<id> (§17.4), only on an otherwise clean
    tree."""
    tag = f"snapshot-{snapshot}"
    if no_commit:
        log("not recording in git (--no-commit)")
        return {"recorded": False, "reason": "--no-commit"}
    repo = repository_state()
    if repo["dirty"]:
        log(f"not recording {tag} in git: uncommitted changes outside the refs files "
            f"({', '.join(repo['changed_files'])})")
        return {"recorded": False, "reason": "dirty tree"}
    files = SELECTION_FILES
    subprocess.run(["git", "-C", REPO, "add", "--", *files], check=True)
    staged = subprocess.run(["git", "-C", REPO, "diff", "--cached", "--quiet", "--", *files])
    if staged.returncode != 0:
        subprocess.run(["git", "-C", REPO, "commit", "--quiet", "-m", f"snapshot {snapshot}",
                        "--", *files], check=True)
    commit = run(["git", "-C", REPO, "rev-parse", "HEAD"])
    subprocess.run(["git", "-C", REPO, "tag", tag, commit], check=True)
    log(f"recorded {tag} at {commit[:12]}")
    return {"recorded": True, "commit": commit, "tag": tag}


def default_arch():
    machine = platform.machine().lower()
    return {"arm64": "aarch64", "amd64": "x86_64"}.get(machine, machine)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arch", default=default_arch())
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("resolve", help="pin tracked components and open an integration")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--force", action="store_true", help="integrate even if nothing changed")
    group.add_argument("--frozen", action="store_true",
                       help="keep every tracked component at the commits of `latest` (development cycle)")
    p = sub.add_parser("record", help="close the open integration")
    p.add_argument("--result", choices=["green", "failed", "aborted"], required=True)
    p.add_argument("--no-commit", action="store_true",
                   help="do not commit the refs or tag snapshot-<id> (green only)")
    args = parser.parse_args()
    return cmd_resolve(args) if args.command == "resolve" else cmd_record(args)


if __name__ == "__main__":
    sys.exit(main())
