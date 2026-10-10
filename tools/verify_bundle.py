#!/usr/bin/env python3
"""Verify every pinned byte in this repository, and optionally reproduce the patched module.

Pins cover the four shipped files. `--reproduce` additionally runs
`patch_kernelsu_module.py` against the included upstream copy and requires the result to
match `module/kernelsu-gxr.ko` byte for byte.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PINS = {
    "module/kernelsu-gxr.ko": (
        "f528ef24fca78fe429df7e7290058febf884e97dc533497549c345c5e8d3e2d6", 468768),
    "module/kernelsu-android12-5.10-upstream.ko": (
        "b6075e6ebff6d1b76b64b322086162f58787d747614edc1a04e92db7c4ae8e21", 468768),
    "manager/KernelSU_Next_v3.4.0-android12-5.10_33303-release.apk": (
        "94eb18574318c00c67a8903abf07ccb5cbfedf13701fbbbf8fa26850f91fddf7", 6788732),
    "tools/patch_kernelsu_module.py": (
        "a9ba7e11d370423b6972bc573320fc7ad5852a4c3239ea210119637dd138bbe7", 6291),
}

PATCHER = "tools/patch_kernelsu_module.py"
MODULE = "module/kernelsu-gxr.ko"
UPSTREAM = "module/kernelsu-android12-5.10-upstream.ko"


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_pins(root=ROOT) -> list[str]:
    """Returns a list of problems; empty means every pinned file matches."""
    problems = []
    for relative, (expected_sha, expected_size) in PINS.items():
        path = Path(root) / relative
        if not path.is_file():
            problems.append(f"{relative}: missing")
            continue
        if path.stat().st_size != expected_size:
            problems.append(f"{relative}: size {path.stat().st_size} != {expected_size}")
        actual = digest(path)
        if actual != expected_sha:
            problems.append(f"{relative}: sha256 {actual} != {expected_sha}")
        else:
            print(f"OK {relative} {actual}")
    return problems


def check_patch(root=ROOT) -> list[str]:
    result = subprocess.run(
        [sys.executable, str(Path(root) / PATCHER), "--verify", str(Path(root) / MODULE),
         "--upstream", str(Path(root) / UPSTREAM)],
        capture_output=True, text=True)
    if result.returncode != 0:
        return [f"patch_kernelsu_module.py --verify failed: "
                f"{result.stdout.strip()}{result.stderr.strip()}"]
    print(result.stdout.strip())
    return []


def check_reproduce(root=ROOT) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="ksu-reproduce-") as temporary:
        out = Path(temporary) / "kernelsu-gxr.ko"
        result = subprocess.run(
            [sys.executable, str(Path(root) / PATCHER), "--upstream", str(Path(root) / UPSTREAM),
             "--out", str(out)], capture_output=True, text=True)
        if result.returncode != 0:
            return [f"patcher failed: {result.stdout.strip()}{result.stderr.strip()}"]
        actual = digest(out)
        if actual != PINS[MODULE][0]:
            return [f"rebuilt module sha256 {actual} != {PINS[MODULE][0]}"]
        print(f"OK reproduced {MODULE} from the included upstream ({actual})")
    return []


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Verify the pinned bytes of this repository")
    parser.add_argument("--reproduce", action="store_true",
                        help="also rebuild kernelsu-gxr.ko from the included upstream copy")
    arguments = parser.parse_args(argv)
    problems = check_pins() + check_patch()
    if arguments.reproduce:
        problems.extend(check_reproduce())
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    print("All pins verified"
          + ("; module reproduced byte for byte" if arguments.reproduce else "") + ".")
    return 0


if __name__ == "__main__":
    sys.exit(main())
