#!/usr/bin/env python3
"""Publish a verified release: draft -> upload -> verify assets -> published.

Idempotent: an already published release for the tag is left alone, a failed upload stays a
draft, and an existing tag is never moved. Requires the GitHub CLI (`gh`) with a
`contents: write` token in `GH_TOKEN`.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PublishError(RuntimeError):
    pass


def gh(*arguments, check=True):
    result = subprocess.run(["gh", *arguments], cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=300, check=False)
    if check and result.returncode:
        raise PublishError(f"gh {' '.join(arguments)} failed: {result.stderr.strip()}")
    return result


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def parse_sums(path):
    entries = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        checksum, name = line.split(None, 1)
        entries[name.strip()] = checksum.strip()
    return entries


def verify_local_sums(assets):
    sums = next((asset for asset in assets if asset.name == "SHA256SUMS"), None)
    if sums is None:
        return
    entries = parse_sums(sums)
    for asset in assets:
        if asset.name == "SHA256SUMS" or asset.name not in entries:
            continue
        actual = digest(asset)
        if actual != entries[asset.name]:
            raise PublishError(f"{asset.name}: sha256 {actual} != {entries[asset.name]}")


def publish(tag, assets, title=None, notes_file=None):
    assets = [Path(asset).resolve() for asset in assets]
    for asset in assets:
        if not asset.is_file():
            raise PublishError(f"asset missing: {asset}")
    verify_local_sums(assets)

    view = gh("release", "view", tag, "--json", "isDraft", check=False)
    if view.returncode == 0:
        if '"isDraft":true' not in view.stdout.replace(" ", ""):
            print(f"Release {tag} is already published; nothing to do.")
            return 0
        print(f"Release {tag} is a draft; uploading assets.")
        gh("release", "upload", tag, "--clobber", *[str(asset) for asset in assets])
    else:
        create = ["release", "create", tag, "--title",
                  title or f"KernelSU-Next for Galaxy XR {tag}", "--draft"]
        create += (["--notes-file", str(notes_file)] if notes_file else ["--generate-notes"])
        gh(*create, *[str(asset) for asset in assets])

    listed = gh("release", "view", tag, "--json", "assets")
    present = {entry["name"] for entry in json.loads(listed.stdout).get("assets", [])}
    missing = [asset.name for asset in assets if asset.name not in present]
    if missing:
        raise PublishError(f"release is missing uploaded assets: {missing}")
    gh("release", "edit", tag, "--draft=false", "--latest")
    print(f"Published {tag} with {len(assets)} assets.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Publish a verified GitHub Release")
    parser.add_argument("--tag", required=True, help="release tag, e.g. v3.4.0-gxr.1")
    parser.add_argument("--asset", required=True, action="append", type=Path,
                        help="asset to upload; repeatable")
    parser.add_argument("--title")
    parser.add_argument("--notes-file", type=Path)
    arguments = parser.parse_args()
    try:
        return publish(arguments.tag, arguments.asset, arguments.title, arguments.notes_file)
    except PublishError as error:
        print(f"Publish failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
