import os
from pathlib import Path
import re
import subprocess
import sys


SKILL_NAME = "even-effort-pace-chart"
SKILL_PATH = f"skills/{SKILL_NAME}"
VERSION_PATTERN = re.compile(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")


def run(command, repo):
    return subprocess.run(command, cwd=repo, check=True, capture_output=True, text=True)


def versions(tags):
    found = []
    for tag in tags.splitlines():
        match = VERSION_PATTERN.fullmatch(tag)
        if match:
            found.append((tuple(int(part) for part in match.groups()), tag))
    return found


def publish(commit, output_dir, repo):
    run(["git", "fetch", "--tags", "origin"], repo)
    existing = versions(run(["git", "tag", "--points-at", commit], repo).stdout)

    if existing:
        tag = max(existing)[1]
    else:
        available = versions(run(["git", "tag", "--list", "v*"], repo).stdout)
        if available:
            major, minor, patch = max(available)[0]
            tag = f"v{major}.{minor}.{patch + 1}"
        else:
            tag = "v1.0.0"
        run(["git", "tag", tag, commit], repo)

    archive = Path(output_dir) / f"{SKILL_NAME}-{tag}.zip"
    run(
        [
            "git", "archive", "--format=zip", f"--prefix={SKILL_NAME}/",
            f"--output={archive}", f"{tag}:{SKILL_PATH}",
        ],
        repo,
    )

    if not existing:
        run(["git", "push", "origin", f"refs/tags/{tag}"], repo)

    repository = os.environ["GITHUB_REPOSITORY"]
    response = subprocess.run(
        ["gh", "api", "--silent", f"repos/{repository}/releases/tags/{tag}"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if response.returncode == 0:
        run(["gh", "release", "upload", tag, str(archive), "--clobber"], repo)
    elif "(HTTP 404)" in response.stderr:
        run(
            [
                "gh", "release", "create", tag, str(archive), "--verify-tag",
                "--title", tag, "--notes", f"Skill package from commit {commit}.",
            ],
            repo,
        )
    else:
        raise subprocess.CalledProcessError(
            response.returncode, response.args, output=response.stdout, stderr=response.stderr
        )
    print(f"Published {archive.name} for {tag}")
    return tag


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: release_skill.py COMMIT OUTPUT_DIR")
    try:
        publish(sys.argv[1], Path(sys.argv[2]), Path.cwd())
    except subprocess.CalledProcessError as error:
        if error.stderr:
            print(error.stderr, file=sys.stderr, end="")
        raise SystemExit(error.returncode) from error
