"""Release against disposable bare Git remotes. No network or user Git settings."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = (
    "plugins/portfolio-analyser/.codex-plugin/plugin.json",
    "plugins/portfolio-analyser/.claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
)


class PublishTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        self.repo = directory / "work"
        self.repo.mkdir()
        self.remote = directory / "target.git"
        self.env = {
            **os.environ,
            "HOME": str(directory),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
        }
        self.git("init", "--bare", "-b", "main", self.remote)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Release Test")
        self.git("config", "user.email", "fixture@example.test")
        for name in (*MANIFESTS, ".githooks/pre-push", "scripts/publish.py"):
            path = self.repo / name
            path.parent.mkdir(exist_ok=True, parents=True)
            shutil.copy2(ROOT / name, path)
        self.set_versions("1.2.3")
        self.git("add", ".")
        self.git("commit", "-m", "Initial test release")
        self.git("remote", "add", "origin", self.remote)
        self.git("push", "-u", "origin", "main")
        subprocess.run(
            [sys.executable, "scripts/publish.py", "setup"],
            cwd=self.repo,
            env=self.env,
            check=True,
            capture_output=True,
        )

    def git(self, *args, check=True):
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo,
            env=self.env,
            capture_output=True,
            text=True,
            check=check,
        )
        return result.stdout.strip() if check else result

    def set_versions(self, version, paths=MANIFESTS):
        for name in paths:
            path = self.repo / name
            data = json.loads(path.read_text())
            manifest = data["plugins"][0] if name == MANIFESTS[2] else data
            manifest["version"] = version
            path.write_text(json.dumps(data, indent=2) + "\n")

    def change(self, name):
        (self.repo / name).write_text("new content\n")
        self.git("add", name)
        self.git("commit", "-m", f"Change {name}")

    def assert_published(self, version, target="main"):
        head = self.git("rev-parse", "HEAD")
        self.assertEqual(self.git("--git-dir", self.remote, "rev-parse", target), head)
        for name in MANIFESTS:
            data = json.loads(
                self.git("--git-dir", self.remote, "show", f"{target}:{name}")
            )
            manifest = data["plugins"][0] if name == MANIFESTS[2] else data
            self.assertEqual(manifest["version"], version)

    def test_auto_patch_docs_and_code_noop_and_unrelated_staged_file(self):
        self.change("README.md")
        self.assertNotEqual(self.git("push", check=False).returncode, 0)
        (self.repo / "draft").write_text("unrelated")
        self.git("add", "draft")
        self.git("publish")
        self.assert_published("1.2.4")
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "draft")
        self.assertEqual(
            set(self.git("diff", "--name-only", "HEAD^", "HEAD").splitlines()),
            set(MANIFESTS),
        )
        head = self.git("rev-parse", "HEAD")
        self.git("publish")
        self.assertEqual(head, self.git("rev-parse", "HEAD"))
        self.git("restore", "--staged", "draft")
        self.change("code.py")
        self.git("publish")
        self.assert_published("1.2.5")

    def test_existing_higher_release_keeps_commit_and_partial_bump_synchronizes(self):
        self.set_versions("2.0.0")
        self.git("commit", "-am", "Major release")
        head = self.git("rev-parse", "HEAD")
        self.git("publish")
        self.assertEqual(head, self.git("rev-parse", "HEAD"))
        self.set_versions("2.1.0", MANIFESTS[:1])
        self.git("commit", "-am", "Select next minor")
        self.git("publish")
        self.assert_published("2.1.0")

    def test_remote_rejection_retry_reuses_bump(self):
        self.change("README.md")
        hook = self.remote / "hooks/pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        self.assertNotEqual(self.git("publish", check=False).returncode, 0)
        head = self.git("rev-parse", "HEAD")
        hook.unlink()
        self.git("publish")
        self.assertEqual(head, self.git("rev-parse", "HEAD"))
        self.assert_published("1.2.4")

    def test_separate_push_destination_and_explicit_branch(self):
        self.git("--git-dir", self.remote, "branch", "release", "main")
        self.git("remote", "set-url", "--push", "origin", self.remote)
        self.git("remote", "set-url", "origin", self.repo / "no-fetch-remote")
        self.change("code.py")
        self.git("publish", "origin", "release")
        self.assert_published("1.2.4", "release")

    def test_divergent_target_is_preserved(self):
        self.change("a")
        other = self.git("rev-parse", "HEAD")
        self.git("--git-dir", self.remote, "fetch", self.repo, "HEAD:main")
        self.git("checkout", "-b", "local", "HEAD^")
        self.change("b")
        self.assertNotEqual(
            self.git("publish", "origin", "main", check=False).returncode, 0
        )
        self.assertEqual(self.git("--git-dir", self.remote, "rev-parse", "main"), other)
