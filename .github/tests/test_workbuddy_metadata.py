import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "even-effort-pace-chart"


class WorkBuddyMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        content = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", content, re.DOTALL)
        if match is None:
            raise AssertionError("SKILL.md must begin with YAML frontmatter")
        cls.frontmatter = match.group(1)

    def field(self, name):
        values = re.findall(
            rf"(?m)^{re.escape(name)}:[ \t]*(.*?)\s*$",
            self.frontmatter,
        )
        self.assertEqual(len(values), 1, f"Expected one {name} field")
        self.assertTrue(values[0].strip(), f"{name} must not be empty")
        return values[0]

    def test_required_workbuddy_fields_are_present(self):
        for name in (
            "name", "display_name", "display_name_en", "description",
            "description_zh", "description_en", "version", "author",
        ):
            with self.subTest(field=name):
                self.field(name)

    def test_workbuddy_examples_are_nonempty_lists(self):
        for name in ("examples_zh", "examples_en"):
            with self.subTest(field=name):
                examples = json.loads(self.field(name))
                self.assertIsInstance(examples, list)
                self.assertGreaterEqual(len(examples), 2)
                self.assertTrue(all(isinstance(item, str) and item.strip() for item in examples))

    def test_chinese_search_metadata_mentions_trail_running(self):
        self.assertEqual(self.field("display_name"), self.field("displayName"))
        self.assertIn("越野跑", self.field("display_name"))
        self.assertIn("越野跑", self.field("description_zh"))
        examples = json.loads(self.field("examples_zh"))
        self.assertTrue(any("越野跑" in example for example in examples))

    def test_packaged_license_matches_repository_license(self):
        self.assertEqual((SKILL / "LICENSE").read_bytes(), (ROOT / "LICENSE").read_bytes())


if __name__ == "__main__":
    unittest.main()
