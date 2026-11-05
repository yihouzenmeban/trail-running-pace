import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release_skill.py"
SPEC = importlib.util.spec_from_file_location("release_skill", SCRIPT)
release_skill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_skill)


class FakeGitHub:
    def __init__(self):
        self.run_command = subprocess.run
        self.releases = {}
        self.created = []
        self.uploaded = []
        self.api_error = None

    def run(self, command, *args, **kwargs):
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

        self.write("skills/even-effort-pace-chart/SKILL.md", "committed skill")
        self.write("skills/even-effort-pace-chart/scripts/pace_chart.py", "committed script")
        self.write("skills/even-effort-pace-chart/references/model.md", "committed reference")
        self.write("skills/even-effort-pace-chart/tests/test_example.py", "committed test")
        self.write("README.md", "outside the skill")
        self.first_commit = self.commit("initial")
        self.git("push", "-u", "origin", "main")
        self.github = FakeGitHub()

    def git(self, *arguments):
        result = subprocess.run(
            ["git", *arguments], cwd=self.repo, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()

    def write(self, relative_path, content):
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def commit(self, message):
        self.git("add", ".")
        self.git(
            "-c", "user.name=Release Test", "-c", "user.email=release-test@example.invalid",
            "commit", "-m", message,
        )
        return self.git("rev-parse", "HEAD")

    def publish(self, commit):
        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "example/pace"}):
            with mock.patch.object(release_skill.subprocess, "run", side_effect=self.github.run):
                return release_skill.publish(commit, self.artifacts, self.repo)

    def test_first_release_packages_committed_skill_and_rerun_reuses_it(self):
        self.assertEqual(self.publish(self.first_commit), "v1.0.0")
        self.assertEqual(
            self.git("ls-remote", "origin", "refs/tags/v1.0.0").split()[0],
            self.first_commit,
        )
        release = self.github.releases["v1.0.0"]
        self.assertEqual(release["name"], "even-effort-pace-chart-v1.0.0.zip")
        self.assertEqual(
            set(release["files"]),
            {
                "even-effort-pace-chart/SKILL.md",
                "even-effort-pace-chart/scripts/pace_chart.py",
                "even-effort-pace-chart/references/model.md",
                "even-effort-pace-chart/tests/test_example.py",
            },
        )
        self.assertEqual(release["files"]["even-effort-pace-chart/SKILL.md"], b"committed skill")

        self.write("skills/even-effort-pace-chart/SKILL.md", "uncommitted change")
        self.write("skills/even-effort-pace-chart/untracked.txt", "untracked")
        self.assertEqual(self.publish(self.first_commit), "v1.0.0")
        self.assertEqual(self.github.created, ["v1.0.0"])
        self.assertEqual(self.github.uploaded, ["v1.0.0"])
        self.assertEqual(
            self.github.releases["v1.0.0"]["files"]["even-effort-pace-chart/SKILL.md"],
            b"committed skill",
        )
        self.assertNotIn(
            "even-effort-pace-chart/untracked.txt", self.github.releases["v1.0.0"]["files"]
        )

    def test_uses_numeric_version_order_and_ignores_nonrelease_tags(self):
        for tag in ("v1.9.9", "v1.10.2", "v1.10.11", "v99.0.0-rc.1", "other"):
            self.git("tag", tag, self.first_commit)
            self.git("push", "origin", tag)
        self.write("skills/even-effort-pace-chart/SKILL.md", "next revision")
        next_commit = self.commit("next")

        self.assertEqual(self.publish(next_commit), "v1.10.12")
        self.assertEqual(
            self.github.releases["v1.10.12"]["files"]["even-effort-pace-chart/SKILL.md"],
            b"next revision",
        )

    def test_fetches_remote_tags_before_selecting_version(self):
        subprocess.run(
            ["git", "--git-dir", str(self.remote), "tag", "v2.0.6", self.first_commit],
            check=True,
            capture_output=True,
        )
        self.write("skills/even-effort-pace-chart/SKILL.md", "new revision")
        next_commit = self.commit("next")

        self.assertEqual(self.publish(next_commit), "v2.0.7")

    def test_packages_triggering_commit_when_head_has_moved(self):
        self.write("skills/even-effort-pace-chart/SKILL.md", "newer revision")
        self.commit("newer")

        self.assertEqual(self.publish(self.first_commit), "v1.0.0")
        self.assertEqual(
            self.github.releases["v1.0.0"]["files"]["even-effort-pace-chart/SKILL.md"],
            b"committed skill",
        )
        self.assertEqual(
            self.git("ls-remote", "origin", "refs/tags/v1.0.0").split()[0],
            self.first_commit,
        )

    def test_api_failure_stops_release_and_rerun_reuses_pushed_tag(self):
        self.github.api_error = "gh: Forbidden (HTTP 403)\n"
        with self.assertRaises(subprocess.CalledProcessError):
            self.publish(self.first_commit)
        self.assertEqual(self.github.created, [])
        self.assertEqual(self.github.uploaded, [])
        self.assertEqual(
            self.git("ls-remote", "origin", "refs/tags/v1.0.0").split()[0],
            self.first_commit,
        )

        self.github.api_error = None
        self.assertEqual(self.publish(self.first_commit), "v1.0.0")
        self.assertEqual(self.github.created, ["v1.0.0"])


if __name__ == "__main__":
    unittest.main()
