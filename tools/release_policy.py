#!/usr/bin/env python3
"""Version and publish policy for the KernelSU-Next-GXR repository.

Version truth lives in `VERSION` (`<upstream>-gxr.<n>`, e.g. `3.4.0-gxr.1`). This module is
its only writer; `tools/verify_release_version.py` fails the run when a pushed tag disagrees.

Commit prefixes drive the adaptation revision: a `fix:`, `feat:` or `rework:` commit bumps
`gxr.<n>` by one. Any other prefix bumps nothing -- project policy, not vanilla
Conventional Commits.

Publish gate (design notes: GitHub-CI-Notes-2026-10-10.md in the gxr-kernel project):

* pushed tag `v<x.y.z-gxr.n>` -- publish only when it equals the source version;
* `refs/heads/main` -- publish when the source version is ahead of the newest `v*` tag, or
  when the commits after that tag ask for a revision bump. A `chore(release):` commit never
  counts, and a version already ahead of the tag is published as-is, so a re-run cannot
  double-bump;
* manual dispatch with `publish: true` -- publish the source version unchanged.

Every other push and every pull request is a verify-only dry run.

Modes:

* default (plan) -- print the decision and write it to `$GITHUB_OUTPUT`;
* `--persist`     -- write the planned version into `VERSION` and the changelog;
* `--commit`      -- deterministic bot commit for the persisted bump, push to `main`.
"""

import argparse
import datetime
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
CHANGELOG = ROOT / "CHANGELOG.md"

VERSION_RE = re.compile(r"^(\d+\.\d+\.\d+)-gxr\.(\d+)$")
TAG_RE = re.compile(r"v(\d+\.\d+\.\d+-gxr\.\d+)\Z")

PREFIXES = (("rework:", "major"), ("feat:", "minor"), ("fix:", "patch"))
RANK = {"patch": 1, "minor": 2, "major": 3}
GROUPS = (("major", "Reworks"), ("minor", "Features"), ("patch", "Fixes"))
BOT_NAME = "github-actions[bot]"
BOT_MAIL = "41898282+github-actions[bot]@users.noreply.github.com"


class PolicyError(RuntimeError):
    pass


def git(*arguments):
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True,
                          text=True, check=False, timeout=60)


def parse_version(text):
    match = VERSION_RE.match(text.strip())
    if not match:
        raise PolicyError(f"Not a <x.y.z>-gxr.<n> version: {text!r}")
    return tuple(int(part) for part in match.group(1).split(".")) + (int(match.group(2)),)


def format_version(parts):
    return ".".join(str(part) for part in parts[:3]) + f"-gxr.{parts[3]}"


def bump(version):
    parts = parse_version(version)
    return format_version(parts[:3] + (parts[3] + 1,))


def read_version(root=ROOT):
    text = (root / "VERSION").read_text(encoding="utf-8").strip()
    parse_version(text)
    return text


def tags_by_version():
    output = git("tag", "--list", "v*").stdout.split()
    found = {}
    for tag in output:
        match = TAG_RE.match(tag)
        if match:
            found[parse_version(match.group(1))] = match.group(1)
    return found


def newest_tag():
    found = tags_by_version()
    return format_version(max(found)) if found else None


def commit_subjects(since_version=None):
    arguments = ["log", "--pretty=%s"]
    if since_version:
        arguments.insert(1, f"v{since_version}..HEAD")
    result = git(*arguments)
    if result.returncode:
        raise PolicyError(f"git log failed: {result.stderr.strip()}")
    return [line for line in result.stdout.splitlines() if line.strip()]


def requested_delta(subjects):
    highest = None
    for subject in subjects:
        if subject.startswith("chore(release):"):
            continue
        for prefix, delta in PREFIXES:
            if subject.startswith(prefix):
                if highest is None or RANK[delta] > RANK[highest]:
                    highest = delta
                break
    return highest


def plan(ref=None, event=None, dispatch_publish=False):
    ref = ref if ref is not None else os.environ.get("GITHUB_REF", "")
    event = event if event is not None else os.environ.get("GITHUB_EVENT_NAME", "")
    current = read_version()
    newest = newest_tag()
    decision = {"current": current, "version": current, "publish": False, "bump": False,
                "tag": f"v{current}", "delta": None, "reason": ""}

    tag_match = TAG_RE.match(ref.removeprefix("refs/tags/")) if ref.startswith("refs/tags/") else None
    if tag_match:
        tagged = tag_match.group(1)
        if tagged != current:
            raise PolicyError(f"tag v{tagged} does not match source version {current}")
        decision["reason"] = f"tag v{tagged} matches the source version"
        decision["publish"] = True
        return decision

    if dispatch_publish:
        if newest is not None and parse_version(current) < parse_version(newest):
            decision["reason"] = f"source {current} is behind the newest tag v{newest}"
            return decision
        decision["reason"] = "manual dispatch requested publish"
        decision["publish"] = True
        return decision

    if ref == "refs/heads/main":
        if newest is None:
            decision["reason"] = "first release: no v* tag exists yet"
            decision["publish"] = True
        elif parse_version(current) > parse_version(newest):
            decision["reason"] = f"source {current} is ahead of the newest tag v{newest}"
            decision["publish"] = True
        elif parse_version(current) == parse_version(newest):
            delta = requested_delta(commit_subjects(newest))
            if delta is None:
                decision["reason"] = f"no bump commits since v{newest}"
            else:
                decision["version"] = bump(current)
                decision["tag"] = f"v{decision['version']}"
                decision["delta"] = delta
                decision["bump"] = True
                decision["publish"] = True
                decision["reason"] = f"adaptation revision bump from {delta}-class commits after v{newest}"
        else:
            decision["reason"] = f"source {current} is behind the newest tag v{newest}"
        return decision

    decision["reason"] = f"dry run for {ref or event or 'this ref'}"
    return decision


def emit(decision, stream=None):
    stream = stream or os.environ.get("GITHUB_OUTPUT")
    pairs = {"version": decision["version"], "publish": str(decision["publish"]).lower(),
             "bump": str(decision["bump"]).lower(), "tag": decision["tag"],
             "delta": decision["delta"] or "", "reason": decision["reason"]}
    if stream:
        with open(stream, "a", encoding="utf-8") as handle:
            for key, value in pairs.items():
                handle.write(f"{key}={value}\n")
    return pairs


def changelog_section(version, delta, subjects, day):
    lines = [f"## [{version}] - {day}", ""]
    headings = {key: title for key, title in GROUPS}
    grouped = {"major": [], "minor": [], "patch": [], "other": []}
    for subject in subjects:
        if subject.startswith("chore(release):"):
            continue
        placed = False
        for prefix, key in PREFIXES:
            if subject.startswith(prefix):
                grouped[key].append(subject)
                placed = True
                break
        if not placed:
            grouped["other"].append(subject)
    for key in ("major", "minor", "patch", "other"):
        if not grouped[key]:
            continue
        lines.append(f"### {headings.get(key, 'Other')}")
        lines.extend(f"- {subject}" for subject in grouped[key])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def persist(decision):
    if not decision["bump"]:
        print("No bump to persist.")
        return 0
    version = decision["version"]
    VERSION_FILE.write_text(version + "\n", encoding="utf-8")

    day = datetime.date.today().isoformat()
    subjects = commit_subjects(newest_tag())
    section = changelog_section(version, decision["delta"], subjects, day)
    existing = CHANGELOG.read_text(encoding="utf-8") if CHANGELOG.exists() else "# Changelog\n"
    head, _, tail = existing.partition("\n## [")
    body = section + ("\n## [" + tail if tail else "")
    CHANGELOG.write_text(head.rstrip() + "\n\n" + body, encoding="utf-8")
    print(f"Persisted version {version}.")
    return 0


def commit(decision):
    if not decision["bump"]:
        print("No bump to commit.")
        return 0
    sha = os.environ.get("GITHUB_SHA") or git("rev-parse", "HEAD").stdout.strip()
    date = git("show", "-s", "--format=%cI", sha).stdout.strip()
    if not date:
        raise PolicyError("Could not read the source commit date")
    message = f"chore(release): v{decision['version']}\n\nRelease-source: {sha}\n"
    environment = dict(os.environ, GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    steps = [["add", "--", "VERSION", "CHANGELOG.md"],
             ["-c", f"user.name={BOT_NAME}", "-c", f"user.email={BOT_MAIL}",
              "commit", "--allow-empty", "-m", message]]
    for step in steps:
        result = subprocess.run(["git", *step], cwd=ROOT, env=environment, capture_output=True,
                                text=True, timeout=60)
        if result.returncode:
            raise PolicyError(f"git {step[0]} failed: {result.stderr.strip()}")
    fetch = git("fetch", "origin", "main")
    if fetch.returncode:
        raise PolicyError(f"git fetch failed: {fetch.stderr.strip()}")
    ancestor = git("merge-base", "--is-ancestor", "origin/main", "HEAD")
    if ancestor.returncode:
        raise PolicyError("main advanced concurrently; refusing to overwrite it")
    push = git("push", "origin", "HEAD:main")
    if push.returncode:
        raise PolicyError(f"git push failed: {push.stderr.strip()}")
    print(f"Pushed chore(release) commit for v{decision['version']}.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Compute and apply the KernelSU-Next-GXR release policy")
    parser.add_argument("--persist", action="store_true", help="write the planned version into VERSION and CHANGELOG")
    parser.add_argument("--commit", action="store_true", help="commit and push the persisted bump")
    parser.add_argument("--ref", help="override GITHUB_REF")
    parser.add_argument("--event", help="override GITHUB_EVENT_NAME")
    parser.add_argument("--dispatch-publish", action="store_true", help="pretend a dispatch asked to publish")
    arguments = parser.parse_args()
    dispatch = arguments.dispatch_publish or (
        (arguments.event or os.environ.get("GITHUB_EVENT_NAME", "")) == "workflow_dispatch"
        and os.environ.get("INPUT_PUBLISH", "").lower() == "true")
    try:
        decision = plan(arguments.ref, arguments.event, dispatch)
        if arguments.persist:
            return persist(decision)
        if arguments.commit:
            return commit(decision)
        emit(decision)
    except PolicyError as error:
        print(f"Release policy failed: {error}", file=sys.stderr)
        return 1
    print(f"current={decision['current']} version={decision['version']} "
          f"publish={str(decision['publish']).lower()} bump={str(decision['bump']).lower()} "
          f"reason={decision['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
