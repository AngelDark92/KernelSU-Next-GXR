import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUNDLE = load("verify_bundle", "tools/verify_bundle.py")
POLICY = load("release_policy", "tools/release_policy.py")


class PinTests(unittest.TestCase):
    def test_every_pinned_file_matches(self):
        self.assertEqual(BUNDLE.check_pins(), [])

    def test_pins_cover_the_shipped_files(self):
        for relative in ("module/kernelsu-gxr.ko",
                         "module/kernelsu-android12-5.10-upstream.ko",
                         "manager/KernelSU_Next_v3.4.0-android12-5.10_33303-release.apk",
                         "tools/patch_kernelsu_module.py"):
            self.assertIn(relative, BUNDLE.PINS)


class PatchTests(unittest.TestCase):
    def test_verify_mode_passes_on_the_shipped_module(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/patch_kernelsu_module.py"),
             "--verify", str(ROOT / "module/kernelsu-gxr.ko"),
             "--upstream", str(ROOT / "module/kernelsu-android12-5.10-upstream.ko")],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_module_reproduces_from_the_included_upstream(self):
        with tempfile.TemporaryDirectory(prefix="ksu-repro-") as temporary:
            out = Path(temporary) / "rebuilt.ko"
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools/patch_kernelsu_module.py"),
                 "--upstream", str(ROOT / "module/kernelsu-android12-5.10-upstream.ko"),
                 "--out", str(out)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(BUNDLE.digest(out), BUNDLE.PINS["module/kernelsu-gxr.ko"][0])


class VersionFileTests(unittest.TestCase):
    def test_version_file_is_well_formed(self):
        self.assertTrue(POLICY.VERSION_RE.match(POLICY.read_version()))

    def test_verify_release_version_passes(self):
        result = subprocess.run([sys.executable, str(ROOT / "tools/verify_release_version.py")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class PolicyTests(unittest.TestCase):
    def test_parse_and_format_round_trip(self):
        self.assertEqual(POLICY.format_version(POLICY.parse_version("3.4.0-gxr.1")), "3.4.0-gxr.1")

    def test_bare_versions_are_rejected(self):
        with self.assertRaises(POLICY.PolicyError):
            POLICY.parse_version("3.4.0")

    def test_bump_increments_only_the_adaptation_revision(self):
        self.assertEqual(POLICY.bump("3.4.0-gxr.1"), "3.4.0-gxr.2")

    def test_requested_delta_takes_the_highest_prefix(self):
        self.assertEqual(POLICY.requested_delta(["chore(release): v3.4.0-gxr.1", "fix: a", "feat: b"]),
                         "minor")

    def test_release_commits_never_trigger_another_bump(self):
        self.assertIsNone(POLICY.requested_delta(["chore(release): v3.4.0-gxr.1"]))

    def test_tag_ref_must_match_the_source_version(self):
        with self.assertRaises(POLICY.PolicyError):
            POLICY.plan(ref="refs/tags/v9.9.9-gxr.9", event="push")
        decision = POLICY.plan(ref=f"refs/tags/v{POLICY.read_version()}", event="push")
        self.assertTrue(decision["publish"])

    def test_first_release_on_main_publishes_without_a_bump(self):
        with patch.object(POLICY, "newest_tag", return_value=None):
            decision = POLICY.plan(ref="refs/heads/main", event="push")
        self.assertTrue(decision["publish"])
        self.assertFalse(decision["bump"])

    def test_bump_commits_after_the_newest_tag_raise_the_revision(self):
        with patch.object(POLICY, "newest_tag", return_value=POLICY.read_version()), \
             patch.object(POLICY, "commit_subjects", return_value=["fix: something"]):
            decision = POLICY.plan(ref="refs/heads/main", event="push")
        self.assertTrue(decision["publish"])
        self.assertTrue(decision["bump"])
        self.assertEqual(decision["version"], POLICY.bump(POLICY.read_version()))

    def test_source_behind_the_newest_tag_does_not_publish(self):
        with patch.object(POLICY, "newest_tag", return_value="3.4.0-gxr.9"):
            decision = POLICY.plan(ref="refs/heads/main", event="push")
        self.assertFalse(decision["publish"])

    def test_dispatch_publish_publishes_the_source_version(self):
        with patch.object(POLICY, "newest_tag", return_value=POLICY.read_version()):
            decision = POLICY.plan(ref="refs/heads/main", event="workflow_dispatch",
                                   dispatch_publish=True)
        self.assertTrue(decision["publish"])
        self.assertFalse(decision["bump"])

    def test_other_refs_are_dry_runs(self):
        decision = POLICY.plan(ref="refs/heads/topic", event="push")
        self.assertFalse(decision["publish"])


if __name__ == "__main__":
    unittest.main()
