#!/usr/bin/env python3
"""Fail the run when the version sources disagree.

Checked sources:

* `VERSION` (the single source of truth, `<upstream>-gxr.<n>`),
* an optional pushed tag `v<version>`.

No network, no device access.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAG_RE = re.compile(r"v(\d+\.\d+\.\d+-gxr\.\d+)\Z")


def check(tag=None, root=ROOT):
    sys.path.insert(0, str(root / "tools"))
    import release_policy

    version = release_policy.read_version(root)
    if tag:
        match = TAG_RE.match(tag)
        if not match:
            raise release_policy.PolicyError(f"tag {tag!r} is not v<x.y.z>-gxr.<n>")
        if match.group(1) != version:
            raise release_policy.PolicyError(f"tag {tag} does not match source version {version}")
    print(f"Version sources agree: {version}" + (f", tag {tag}" if tag else ""))
    return 0


def main():
    parser = argparse.ArgumentParser(description="Verify the KernelSU-Next-GXR version sources")
    parser.add_argument("--tag", help="pushed tag to compare against the source version")
    arguments = parser.parse_args()
    try:
        return check(arguments.tag)
    except Exception as error:  # noqa: BLE001 - the CLI reports any policy failure the same way
        print(f"Version check failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
