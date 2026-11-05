import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release_skill.py"
SPEC = importlib.util.spec_from_file_location("release_skill", SCRIPT)
release_skill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_skill)
SKILL = "skills/even-effort-pace-chart"
FRONTMATTER = f"{SKILL}/SKILL.md"
MANIFEST = f"{SKILL}/manifest.yaml"


class FakeGitHub:
    def __init__(self):
        self.run_command = subprocess.run
        self.releases = {}
        self.created = []
        self.uploaded = []
        self.api_error = None
        self.before_push = None

    def run(self, command, *args, **kwargs):
        if command[:3] == ["git", "push", "--atomic"] and self.before_push:
            callback, self.before_push = self.before_push, None
            callback()
        if command[0] != "gh":
            return self.run_command(command, *args, **kwargs)

        if command[1] == "api":
            if self.api_error:
                return subprocess.CompletedProcess(command, 1, "", self.api_error)
            tag = command[-1].rsplit("/", 1)[-1]
            if tag in self.releases:
                return subprocess.CompletedProcess(command, 0, "", "")
            return subprocess.CompletedProcess(command, 1, "", "gh: Not Found (HTTP 404)\n")

        tag = command[3]
        archive = Path(command[4])
        with zipfile.ZipFile(archive) as package:
            files = {name: package.read(name) for name in package.namelist() if not name.endswith("/")}
        self.releases[tag] = {"name": archive.name, "files": files}
        if command[2] == "create":
            self.created.append(tag)
        elif command[2] == "upload":
            self.uploaded.append(tag)
        else:
            raise AssertionError(f"Unexpected GitHub command: {command}")
        return subprocess.CompletedProcess(command, 0, "", "")


class ReleaseSkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / "remote.git"
        self.repo = self.root / "repo"
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir()
        subprocess.run(["git", "init", "--bare", str(self.remote)], check=True, capture_output=True)
        subprocess.run(["git", "init", "--initial-branch=main", str(self.repo)], check=True, capture_output=True)
        self.git("remote", "add", "origin", str(self.remote))

        self.write(FRONTMATTER, "---\nname: example\nversion: 1.0.1\n---\ncommitted skill\n")
        self.write(MANIFEST, "name: example\nversion: 1.0.1\n")
        self.write(f"{SKILL}/scripts/pace_chart.py", "committed script")
        self.write(f"{SKILL}/references/model.md", "committed reference")
        self.write(f"{SKILL}/tests/test_example.py", "committed test")
        self.write("README.md", "outside the skill")
        self.first_commit = self.commit("initial")
        self.git("tag", "v1.0.1", self.first_commit)
        self.git("push", "-u", "origin", "main", "--tags")
        self.github = FakeGitHub()

    def git(self, *arguments, repo=None):
        result = subprocess.run(
            ["git", *arguments], cwd=repo or self.repo, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()

    def write(self, relative_path, content, repo=None):
        path = (repo or self.repo) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def commit(self, message, repo=None):
        self.git("add", ".", repo=repo)
        self.git(
            "-c", "user.name=Release Test", "-c", "user.email=release-test@example.invalid",
            "commit", "-m", message, repo=repo,
        )
        return self.git("rev-parse", "HEAD", repo=repo)

    def skill_change(self, text="updated skill"):
        self.write(f"{SKILL}/scripts/pace_chart.py", text)
        commit = self.commit(text)
        self.git("push", "origin", "main")
        return commit

    def publish(self, commit):
        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "example/pace"}):
            with mock.patch.object(release_skill.subprocess, "run", side_effect=self.github.run):
                return release_skill.publish(commit, self.artifacts, self.repo)

    def remote_head(self):
        return self.git("ls-remote", "origin", "refs/heads/main").split()[0]

    def remote_tag(self, tag):
        return self.git("ls-remote", "origin", f"refs/tags/{tag}").split()[0]

    def version_at(self, commit, path):
        return self.git("show", f"{commit}:{path}")

    def test_updates_versions_commits_tags_and_packages_same_revision(self):
        trigger = self.skill_change()
        self.write(FRONTMATTER, "uncommitted change")
        self.write(f"{SKILL}/untracked.txt", "untracked")
        self.assertEqual(self.publish(trigger), "v1.0.2")
        release_commit = self.remote_head()
        self.assertEqual(self.remote_tag("v1.0.2"), release_commit)
        self.assertEqual(self.git("rev-parse", f"{release_commit}^"), trigger)
        self.assertIn(f"Skill-Release-Trigger: {trigger}", self.git("show", "-s", "--format=%B", release_commit))
        self.assertIn("version: 1.0.2", self.version_at(release_commit, FRONTMATTER))
        self.assertIn("version: 1.0.2", self.version_at(release_commit, MANIFEST))
        release = self.github.releases["v1.0.2"]
        self.assertEqual(release["name"], "even-effort-pace-chart-v1.0.2.zip")
        self.assertIn(b"version: 1.0.2", release["files"]["even-effort-pace-chart/SKILL.md"])
        self.assertIn(b"version: 1.0.2", release["files"]["even-effort-pace-chart/manifest.yaml"])
        self.assertEqual(release["files"]["even-effort-pace-chart/scripts/pace_chart.py"], b"updated skill")
        self.assertEqual(
            set(release["files"]),
            {
                "even-effort-pace-chart/SKILL.md",
                "even-effort-pace-chart/manifest.yaml",
                "even-effort-pace-chart/scripts/pace_chart.py",
                "even-effort-pace-chart/references/model.md",
                "even-effort-pace-chart/tests/test_example.py",
            },
        )
        self.assertEqual((self.repo / FRONTMATTER).read_text(), "uncommitted change")

    def test_rerun_reuses_release_commit_and_tag(self):
        trigger = self.skill_change()
        self.publish(trigger)
        release_commit = self.remote_head()
        self.assertEqual(self.publish(trigger), "v1.0.2")
        self.assertEqual(self.remote_head(), release_commit)
        self.assertEqual(self.github.created, ["v1.0.2"])
        self.assertEqual(self.github.uploaded, ["v1.0.2"])

    def test_rerun_after_later_release_reuses_original_version(self):
        first = self.skill_change("first change")
        self.publish(first)
        first_release = self.remote_head()
        self.git("pull", "--ff-only", "origin", "main")
        second = self.skill_change("second change")
        self.publish(second)
        latest = self.remote_head()

        self.assertEqual(self.publish(first), "v1.0.2")
        self.assertEqual(self.remote_head(), latest)
        self.assertEqual(self.remote_tag("v1.0.2"), first_release)
        self.assertEqual(self.github.created, ["v1.0.2", "v1.0.3"])

    def test_api_failure_retries_existing_version_without_increment(self):
        trigger = self.skill_change()
        self.github.api_error = "gh: Forbidden (HTTP 403)\n"
        with self.assertRaises(subprocess.CalledProcessError):
            self.publish(trigger)
        release_commit = self.remote_head()
        self.assertEqual(self.remote_tag("v1.0.2"), release_commit)
        self.github.api_error = None
        self.assertEqual(self.publish(trigger), "v1.0.2")
        self.assertEqual(self.remote_head(), release_commit)
        self.assertEqual(self.github.created, ["v1.0.2"])

    def test_queued_pushes_package_latest_main_and_increment_each_time(self):
        first = self.skill_change("first change")
        second = self.skill_change("second change")
        self.assertEqual(self.publish(first), "v1.0.2")
        self.assertEqual(
            self.github.releases["v1.0.2"]["files"]["even-effort-pace-chart/scripts/pace_chart.py"],
            b"second change",
        )
        self.assertEqual(self.publish(second), "v1.0.3")
        self.assertIn("version: 1.0.3", self.version_at(self.remote_head(), MANIFEST))

    def test_retries_if_main_advances_before_atomic_push(self):
        trigger = self.skill_change()

        def advance_main():
            other = self.root / "other"
            subprocess.run(["git", "clone", "-b", "main", str(self.remote), str(other)], check=True, capture_output=True)
            self.write("README.md", "concurrent update", repo=other)
            self.commit("concurrent update", repo=other)
            self.git("push", "origin", "main", repo=other)

        self.github.before_push = advance_main
        self.assertEqual(self.publish(trigger), "v1.0.2")
        self.assertEqual(self.version_at(self.remote_head(), "README.md"), "concurrent update")
        self.assertEqual(self.remote_tag("v1.0.2"), self.remote_head())

    def test_retries_if_new_tag_appears_before_atomic_push(self):
        trigger = self.skill_change()

        def create_tag():
            subprocess.run(
                ["git", "--git-dir", str(self.remote), "tag", "v1.0.2", self.first_commit],
                check=True,
                capture_output=True,
            )

        self.github.before_push = create_tag
        self.assertEqual(self.publish(trigger), "v1.0.3")
        self.assertEqual(self.remote_tag("v1.0.2"), self.first_commit)
        self.assertEqual(self.remote_tag("v1.0.3"), self.remote_head())

    def test_invalid_or_mismatched_versions_fail_without_pushing(self):
        for manifest in ("name: example\n", "name: example\nversion: invalid\n", "name: example\nversion: 1.0.0\n"):
            with self.subTest(manifest=manifest):
                self.write(MANIFEST, manifest)
                trigger = self.commit("invalid metadata")
                self.git("push", "origin", "main")
                with self.assertRaises(ValueError):
                    self.publish(trigger)
                self.assertEqual(self.remote_head(), trigger)

    def test_invalid_skill_frontmatter_fails_without_pushing(self):
        for skill in (
            "name: example\nversion: 1.0.1\n",
            "---\nname: example\n---\nversion: 1.0.1\n",
            "---\nversion: invalid\n---\n",
            "---\nversion: 1.0.1\nversion: 1.0.1\n---\n",
        ):
            with self.subTest(skill=skill):
                self.write(FRONTMATTER, skill)
                trigger = self.commit("invalid frontmatter")
                self.git("push", "origin", "main")
                with self.assertRaises(ValueError):
                    self.publish(trigger)
                self.assertEqual(self.remote_head(), trigger)

    def test_trigger_must_be_in_remote_main(self):
        self.write(f"{SKILL}/scripts/pace_chart.py", "not pushed")
        trigger = self.commit("not pushed")
        with self.assertRaises(ValueError):
            self.publish(trigger)
        self.assertEqual(self.remote_head(), self.first_commit)

    def test_uses_highest_version_from_metadata_or_remote_tags(self):
        self.git("tag", "v1.9.9", self.first_commit)
        self.git("tag", "v1.10.2", self.first_commit)
        self.git(
            "-c", "user.name=Release Test", "-c", "user.email=release-test@example.invalid",
            "tag", "-a", "v1.10.11", "-m", "release", self.first_commit,
        )
        self.git("tag", "v99.0.0-rc.1", self.first_commit)
        self.git("push", "origin", "--tags")
        trigger = self.skill_change()
        self.assertEqual(self.publish(trigger), "v1.10.12")

    def test_uses_metadata_when_newer_than_tags(self):
        self.write(FRONTMATTER, "---\nname: example\nversion: 2.0.4\n---\n")
        self.write(MANIFEST, "name: example\nversion: 2.0.4\n")
        trigger = self.commit("update metadata")
        self.git("push", "origin", "main")
        self.assertEqual(self.publish(trigger), "v2.0.5")

    def test_fetches_remote_tags_before_selecting_version(self):
        subprocess.run(
            ["git", "--git-dir", str(self.remote), "tag", "v2.0.6", self.first_commit],
            check=True,
            capture_output=True,
        )
        trigger = self.skill_change()
        self.assertEqual(self.publish(trigger), "v2.0.7")

    def test_cli_passes_long_token_to_github_commands(self):
        trigger = self.skill_change()
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        fake_gh = bin_dir / "gh"
        fake_gh.write_text(
            "\n".join(
                [
                    f"#!{sys.executable}",
                    "import hashlib, os, sys",
                    "from pathlib import Path",
                    "digest = hashlib.sha256(os.environ['GH_TOKEN'].encode()).hexdigest()",
                    "if digest != os.environ['EXPECTED_TOKEN_DIGEST']:",
                    "    raise SystemExit('Token was altered')",
                    "if sys.argv[1] == 'api':",
                    "    print('gh: Not Found (HTTP 404)', file=sys.stderr)",
                    "    raise SystemExit(1)",
                    "if sys.argv[1:3] != ['release', 'create']:",
                    "    raise SystemExit('Unexpected GitHub command')",
                    "Path(os.environ['GH_CALL_MARKER']).write_text('created')",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        fake_gh.chmod(0o755)
        token = "ghs_42_" + ".".join(part * 180 for part in ("a", "b", "c"))
        marker = self.root / "release-created"
        environment = os.environ.copy()
        environment.update(
            {
                "PATH": str(bin_dir) + os.pathsep + environment["PATH"],
                "GITHUB_REPOSITORY": "example/pace",
                "GH_TOKEN": token,
                "EXPECTED_TOKEN_DIGEST": hashlib.sha256(token.encode()).hexdigest(),
                "GH_CALL_MARKER": str(marker),
            }
        )

        result = subprocess.run(
            [sys.executable, str(SCRIPT), trigger, str(self.artifacts)],
            cwd=self.repo,
            env=environment,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(marker.read_text(encoding="utf-8"), "created")
        self.assertTrue((self.artifacts / "even-effort-pace-chart-v1.0.2.zip").is_file())


if __name__ == "__main__":
    unittest.main()
