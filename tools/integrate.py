#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Integration cycles (docs/spec.md §17, §31).

  resolve [--force]                          pin every tracked component to an exact commit
  record --result green|failed [--no-commit] publish the snapshot or record the failure

`resolve` reads policy/tracking.toml and writes the resolved refs into project.refs and
junction.refs. It also writes the snapshot id to include/snapshot.yml and starts a
manifest in out/integrations/<id>/. It exits 3 when nothing changed since latest-green.

`record --result green` publishes out/snapshots/<id>/ (manifest, compressed image,
SHA256SUMS) and moves out/snapshots/latest-green.json to it. It then commits the refs and
tags the commit `snapshot-<id>` (§17.4), unless the tree has uncommitted changes outside
the refs files, so tags always match real history. The resolved refs stay in the working
tree: it always holds the latest-green pins. `record --result failed` keeps the manifest
and serial log, and restores the files resolve changed.

An override whose FDSDK original changed fails the cycle at resolve (§31.4).

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
import urllib.request

from ruamel.yaml import YAML

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY = os.path.join(REPO, "policy", "tracking.toml")
SNAPSHOT_YML = os.path.join(REPO, "include", "snapshot.yml")
OUT = os.path.join(REPO, "out")
INTEGRATIONS = os.path.join(OUT, "integrations")
SNAPSHOTS = os.path.join(OUT, "snapshots")
CURRENT = os.path.join(INTEGRATIONS, "current")
LATEST_GREEN = os.path.join(SNAPSHOTS, "latest-green.json")
MIRRORS = os.path.expanduser("~/.cache/beamline/mirrors")
PROJECT = "beamline"

# Files resolve may change; restored on failure.
STATEFUL = ["project.refs", "junction.refs", "include/snapshot.yml"]

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


def gitlab_ci_green(project, branch):
    url = (f"https://gitlab.com/api/v4/projects/{project.replace('/', '%2F')}"
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


def describe(path, sha):
    return run(["git", "-C", path, "describe", "--tags", "--long", "--abbrev=40", sha])


def lag(path, selected, head):
    return int(run(["git", "-C", path, "rev-list", "--count", f"{selected}..{head}"]))


# Resolve ------------------------------------------------------------------------------

def bst_track(arch, elements):
    if elements:
        subprocess.run(["bst", "--no-colors", "--option", "arch", arch, "source", "track",
                        "--deps", "none", *elements], cwd=REPO, check=True)


def resolve_component(name, comp, arch):
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
        sha = gitlab_ci_green(comp["gitlab_project"], branch)
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
COPIED_FROM = re.compile(r"^# Copied from: freedesktop-sdk (?P<sha>[0-9a-f]{40})\n#\s+(?P<path>\S+)", re.M)


def override_drift(fdsdk):
    """Overrides are copies of FDSDK recipes (decisions D15). Report each one whose original
    changed between the recorded FDSDK commit and the selected one (§31.4)."""
    if not os.path.isdir(OVERRIDES):
        return []
    warnings = []
    for name in sorted(os.listdir(OVERRIDES)):
        with open(os.path.join(OVERRIDES, name), encoding="utf-8") as f:
            m = COPIED_FROM.search(f.read())
        if not m or m.group("sha") == fdsdk["commit"]:
            continue
        diff = subprocess.run(["git", "-C", fdsdk["mirror"], "diff", "--quiet", m.group("sha"),
                               fdsdk["commit"], "--", m.group("path")])
        if diff.returncode == 1:
            warnings.append(f"overrides/{name}: FDSDK changed {m.group('path')} since "
                            f"{m.group('sha')[:12]}; re-copy it from {fdsdk['commit'][:12]}")
    return warnings


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


def latest_green():
    if not os.path.exists(LATEST_GREEN):
        return None
    return load_json(os.path.join(SNAPSHOTS, load_json(LATEST_GREEN)["snapshot"], "manifest.json"))


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
        sources = {}
        for name, comp in policy["component"].items():
            log(f"resolving {name} ({comp['branch']})")
            sources[name] = resolve_component(name, comp, args.arch)
        drift = []
        fdsdk = sources.get("freedesktop-sdk", {})
        if fdsdk.get("mirror"):
            drift = override_drift(fdsdk)
        for src in sources.values():
            src.pop("mirror", None)
        repo = repository_state()
        previous = latest_green()
        same_repo = previous and all(previous["repository"].get(k) == repo[k]
                                     for k in ("commit", "uncommitted_sha256"))
        same_sources = previous and {k: v["selected_ref"] for k, v in previous["sources"].items()} \
            == {k: v["selected_ref"] for k, v in sources.items()}
        if same_repo and same_sources and not args.force:
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
            "head_conformity": f"{at_head}/{len(sources)}",
            "fixed": policy.get("fixed", {}),
            "override_drift": drift,
            "provenance": provenance(),
        }
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
        pinned = " PINNED" if src["status"] == "PINNED" else ""
        log(f"  {name:18} {src['selected_ref']}{pinned}")
    if repo["dirty"]:
        log(f"warning: uncommitted changes outside refs files: {', '.join(repo['changed_files'])}")
    return 0


# Record -------------------------------------------------------------------------------

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


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
    previous = latest_green()
    image_dir = os.path.join(OUT, args.arch, "virt")
    serial = os.path.join(image_dir, "serial.log")

    if args.result == "failed":
        manifest["result"] = "failed"
        manifest["changed_since_green"] = changed_since(manifest, previous)
        if os.path.exists(serial):
            shutil.copyfile(serial, os.path.join(workdir, "serial.log"))
        write_json(os.path.join(workdir, "manifest.json"), manifest)
        restore(snapshot)
        os.remove(CURRENT)
        log(f"integration {snapshot} FAILED; latest-green unchanged "
            f"({previous['snapshot'] if previous else 'none'})")
        log(f"inputs changed since latest-green: {', '.join(manifest['changed_since_green']) or 'none'}")
        log(f"record: {workdir}")
        return 0

    dest = os.path.join(SNAPSHOTS, snapshot)
    os.makedirs(dest)
    image = os.path.join(image_dir, "disk.raw")
    name = f"virt-{args.arch}.disk.raw"
    log(f"compressing {name}")
    subprocess.run(["zstd", "-q", "-T0", "-10", image, "-o", os.path.join(dest, name + ".zst")], check=True)
    if os.path.exists(serial):
        shutil.copyfile(serial, os.path.join(dest, f"virt-{args.arch}.serial.log"))

    manifest["result"] = "green"
    manifest["changed_since_green"] = changed_since(manifest, previous)
    manifest["artifacts"] = {name: {"sha256": sha256(image), "zst": name + ".zst",
                                    "zst_sha256": sha256(os.path.join(dest, name + ".zst"))}}
    write_snapshot_id("dev")
    manifest["git"] = record_in_git(snapshot, args.no_commit)
    write_json(os.path.join(dest, "manifest.json"), manifest)
    with open(os.path.join(dest, "SHA256SUMS"), "w") as f:
        for fname in sorted(os.listdir(dest)):
            if fname != "SHA256SUMS":
                f.write(f"{sha256(os.path.join(dest, fname))}  {fname}\n")
    write_json(LATEST_GREEN, {"snapshot": snapshot})

    shutil.rmtree(workdir)
    os.remove(CURRENT)
    log(f"snapshot {snapshot} GREEN: latest-green → {snapshot} ({manifest['head_conformity']} at HEAD)")
    return 0


def record_in_git(snapshot, no_commit):
    """Commit the refs and tag snapshot-<id> (§17.4), only on an otherwise clean tree."""
    tag = f"snapshot-{snapshot}"
    if no_commit:
        log("not recording in git (--no-commit)")
        return {"recorded": False, "reason": "--no-commit"}
    repo = repository_state()
    if repo["dirty"]:
        log(f"not recording {tag} in git: uncommitted changes outside the refs files "
            f"({', '.join(repo['changed_files'])})")
        return {"recorded": False, "reason": "dirty tree"}
    files = ["project.refs", "junction.refs"]
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
    p.add_argument("--force", action="store_true", help="integrate even if nothing changed")
    p = sub.add_parser("record", help="close the open integration")
    p.add_argument("--result", choices=["green", "failed"], required=True)
    p.add_argument("--no-commit", action="store_true",
                   help="do not commit the refs or tag snapshot-<id> (green only)")
    args = parser.parse_args()
    return cmd_resolve(args) if args.command == "resolve" else cmd_record(args)


if __name__ == "__main__":
    sys.exit(main())
