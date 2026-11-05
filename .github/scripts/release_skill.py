import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


SKILL_NAME = "even-effort-pace-chart"
SKILL_PATH = f"skills/{SKILL_NAME}"
SKILL_FILE = f"{SKILL_PATH}/SKILL.md"
MANIFEST_FILE = f"{SKILL_PATH}/manifest.yaml"
NUMBER = r"(?:0|[1-9][0-9]*)"
VERSION_PATTERN = re.compile(rf"v({NUMBER})\.({NUMBER})\.({NUMBER})")
VERSION_LINE = re.compile(r"(?m)^version:[ \t]*(?P<value>[^\r\n]*)\r?$")
VERSION_VALUE = re.compile(
    rf"""(?P<quote>['"]?)(?P<version>{NUMBER}\.{NUMBER}\.{NUMBER})(?P=quote)[ \t]*(?:#.*)?"""
)
MAX_PUSH_ATTEMPTS = 3


def run(command, repo, **options):
    options.setdefault("text", True)
    if options["text"]:
        options.setdefault("encoding", "utf-8")
    return subprocess.run(command, cwd=repo, check=True, capture_output=True, **options)


def versions(tags):
    found = []
    for tag in tags.splitlines():
        match = VERSION_PATTERN.fullmatch(tag)
        if match:
            found.append((tuple(int(part) for part in match.groups()), tag))
    return found


def remote_state(repo):
    run(["git", "fetch", "--no-tags", "origin", "refs/heads/main"], repo)
    main = run(["git", "rev-parse", "FETCH_HEAD"], repo).stdout.strip()
    refs = run(["git", "ls-remote", "--tags", "origin"], repo).stdout
    tags = {}
    for line in refs.splitlines():
        object_id, ref = line.split("\t", 1)
        name = ref.removeprefix("refs/tags/").removesuffix("^{}")
        tags[name] = object_id
    return main, tags


def read_metadata(repo, commit):
    metadata = {}
    for path in (SKILL_FILE, MANIFEST_FILE):
        document = run(["git", "show", f"{commit}:{path}"], repo, text=False).stdout.decode("utf-8")
        start, end = 0, len(document)
        if path == SKILL_FILE:
            opening = re.match(r"\A---[ \t]*\r?\n", document)
            closing = re.search(r"(?m)^---[ \t]*\r?$", document[opening.end():]) if opening else None
            if not closing:
                raise ValueError(f"{path} must contain YAML frontmatter")
            start, end = opening.end(), opening.end() + closing.start()
        lines = list(VERSION_LINE.finditer(document, start, end))
        value = VERSION_VALUE.fullmatch(lines[0].group("value")) if len(lines) == 1 else None
        if not value:
            raise ValueError(f"{path} must contain one valid version")
        version = tuple(int(part) for part in value.group("version").split("."))
        version_start = lines[0].start("value") + value.start("version")
        version_end = lines[0].start("value") + value.end("version")
        metadata[path] = (document, version, version_start, version_end)
    if metadata[SKILL_FILE][1] != metadata[MANIFEST_FILE][1]:
        raise ValueError("Skill and manifest versions must match")
    return metadata


def version_commit(repo, main, trigger, tag, metadata):
    with tempfile.TemporaryDirectory(prefix="skill-release-") as temporary:
        environment = os.environ.copy()
        environment.update({
            "GIT_INDEX_FILE": str(Path(temporary) / "index"),
            "GIT_AUTHOR_NAME": "github-actions[bot]",
            "GIT_AUTHOR_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
            "GIT_COMMITTER_NAME": "github-actions[bot]",
            "GIT_COMMITTER_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
        })
        run(["git", "read-tree", main], repo, env=environment)
        for path, (document, _, start, end) in metadata.items():
            entry = run(["git", "ls-tree", main, "--", path], repo).stdout.split()
            if not entry or entry[0] not in ("100644", "100755"):
                raise ValueError(f"{path} must be a regular file")
            updated = document[:start] + tag[1:] + document[end:]
            blob = run(
                ["git", "hash-object", "-w", "--stdin"], repo,
                env=environment, input=updated.encode("utf-8"), text=False,
            ).stdout.decode("ascii").strip()
            run(["git", "update-index", "--cacheinfo", f"{entry[0]},{blob},{path}"], repo, env=environment)
        tree = run(["git", "write-tree"], repo, env=environment).stdout.strip()
        message = f"ci: 自动更新技能版本至 {tag}\n\nSkill-Release-Trigger: {trigger}\n"
        return run(
            ["git", "commit-tree", tree, "-p", main], repo, env=environment, input=message
        ).stdout.strip()


def prepare_release(commit, repo):
    trigger = run(["git", "rev-parse", "--verify", f"{commit}^{{commit}}"], repo).stdout.strip()
    for attempt in range(MAX_PUSH_ATTEMPTS):
        main, tags = remote_state(repo)
        try:
            run(["git", "merge-base", "--is-ancestor", trigger, main], repo)
        except subprocess.CalledProcessError as error:
            if error.returncode == 1:
                raise ValueError("Triggering commit is not present in remote main") from error
            raise
        existing = run(
            ["git", "log", "-1", "--format=%H", f"--grep=^Skill-Release-Trigger: {trigger}$", main],
            repo,
        ).stdout.strip()
        if existing:
            metadata = read_metadata(repo, existing)
            tag = "v" + ".".join(str(part) for part in metadata[SKILL_FILE][1])
            if tags.get(tag) != existing:
                raise ValueError(f"Existing release commit does not match remote tag {tag}")
            return existing, tag

        metadata = read_metadata(repo, main)
        available = [metadata[SKILL_FILE][1], *(version for version, _ in versions("\n".join(tags)))]
        major, minor, patch = max(available)
        tag = f"v{major}.{minor}.{patch + 1}"
        release_commit = version_commit(repo, main, trigger, tag, metadata)
        try:
            run([
                "git", "push", "--atomic", "origin",
                f"{release_commit}:refs/heads/main",
                f"{release_commit}:refs/tags/{tag}",
            ], repo)
            return release_commit, tag
        except subprocess.CalledProcessError:
            if attempt + 1 == MAX_PUSH_ATTEMPTS:
                raise
            latest_main, latest_tags = remote_state(repo)
            if latest_main == main and tag not in latest_tags:
                raise
    raise RuntimeError("Unable to publish version commit")


def publish(commit, output_dir, repo):
    release_commit, tag = prepare_release(commit, repo)
    archive = Path(output_dir) / f"{SKILL_NAME}-{tag}.zip"
    run(
        [
            "git", "archive", "--format=zip", f"--prefix={SKILL_NAME}/",
            f"--output={archive}", f"{release_commit}:{SKILL_PATH}",
        ],
        repo,
    )

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
                "--title", tag, "--notes", f"Skill package from commit {release_commit}.",
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
    except ValueError as error:
        raise SystemExit(str(error)) from error
