import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "even-effort-pace-chart"
VERSION = r"(?:0|[1-9][0-9]*)"


class SkillHubMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        content = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", content, re.DOTALL)
        if match is None:
            raise AssertionError("SKILL.md must begin with YAML frontmatter")
        cls.frontmatter = match.group(1)
        cls.manifest = (SKILL / "manifest.yaml").read_text(encoding="utf-8")

    def field(self, document, name):
        values = re.findall(rf"(?m)^{re.escape(name)}:[ \t]*(\S[^\r\n]*)$", document)
        self.assertEqual(len(values), 1, f"Expected one nonempty {name} field")
        value = values[0].strip()
        return json.loads(value) if value.startswith('"') else value

    def test_required_skillhub_metadata_is_valid(self):
        slug = self.field(self.frontmatter, "slug")
        self.assertGreaterEqual(len(slug), 2)
        self.assertLessEqual(len(slug), 128)
        self.assertRegex(slug, r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        self.assertTrue(self.field(self.frontmatter, "displayName"))
        version = self.field(self.frontmatter, "version")
        self.assertRegex(version, rf"^{VERSION}\.{VERSION}\.{VERSION}$")

    def test_scalar_metadata_matches_manifest(self):
        for name in ("slug", "displayName", "version", "summary", "license", "homepage"):
            with self.subTest(field=name):
                self.assertEqual(
                    self.field(self.frontmatter, name),
                    self.field(self.manifest, name),
                )

    def test_tags_match_manifest(self):
        tags = json.loads(self.field(self.frontmatter, "tags"))
        match = re.search(
            r"(?m)^tags:[ \t]*\r?\n((?:[ \t]+-[ \t]+[^\r\n]+\r?\n)+)",
            self.manifest,
        )
        self.assertIsNotNone(match, "Expected a tags list in manifest.yaml")
        manifest_tags = [line.strip()[1:].strip() for line in match.group(1).splitlines()]
        self.assertTrue(tags)
        self.assertEqual(tags, manifest_tags)

    def test_trail_running_search_metadata(self):
        for document, fields in (
            (self.frontmatter, ("displayName", "summary")),
            (self.manifest, ("displayName", "description", "summary")),
        ):
            for name in fields:
                with self.subTest(field=name):
                    self.assertIn("越野跑", self.field(document, name))

        match = re.search(
            r"(?m)^triggers:[ \t]*\r?\n((?:[ \t]+-[ \t]+[^\r\n]+\r?\n)+)",
            self.manifest,
        )
        self.assertIsNotNone(match, "Expected a triggers list in manifest.yaml")
        triggers = [line.strip()[1:].strip() for line in match.group(1).splitlines()]
        self.assertIn("越野跑配速表", triggers)
        self.assertIn("越野跑赛后对照", triggers)


if __name__ == "__main__":
    unittest.main()
