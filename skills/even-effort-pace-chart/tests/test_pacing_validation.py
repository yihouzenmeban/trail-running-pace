import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

EVAL = Path(__file__).resolve().parents[1] / "evals" / "evaluate_pacing.py"


class PacingValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("pacing_validation", EVAL)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def observations(self):
        return {"activities": [
            {"id": "train-1", "split": "train", "time_basis": "moving",
             "segments": [
                 {"distance_km": 10, "ascent_m": 0, "seconds": 1000, "rest_seconds": 100},
                 {"distance_km": 10, "ascent_m": 0, "seconds": 1000, "rest_seconds": 0},
             ]},
            {"id": "validation-1", "split": "validation", "time_basis": "elapsed_unseparated",
             "segments": [
                 {"distance_km": 10, "ascent_m": 0, "seconds": 1000},
                 {"distance_km": 10, "ascent_m": 0, "seconds": 1160},
             ]},
        ]}

    def test_selection_uses_training_only_and_reports_internal_checkpoint_errors(self):
        result = self.module.compare(self.observations(), [
            {"fatigue_half_slowdown": 0}, {"fatigue_half_slowdown": .16},
        ])
        self.assertEqual(result["selected_index"], 0)
        self.assertEqual(result["candidates"][0]["train"]["mean_segment_wape"], 0)
        self.assertGreater(result["candidates"][0]["validation"]["mean_checkpoint_mae_seconds"], 0)
        self.assertAlmostEqual(result["candidates"][1]["validation"]["mean_segment_wape"], 0)
        self.assertEqual(result["activity_counts"], {"train": 1, "validation": 1})
        self.assertEqual(result["time_basis_counts"], {"moving": 1, "elapsed_unseparated": 1})
        changed = self.observations()
        changed["activities"][1]["segments"][0]["seconds"] = 1500
        self.assertEqual(self.module.compare(changed, [{"fatigue_half_slowdown": 0},
                                                     {"fatigue_half_slowdown": .16}])["selected_index"], 0)

    def test_terrain_and_known_stops_are_not_misclassified_as_fatigue(self):
        data = self.observations()
        for activity in data["activities"]:
            activity["time_basis"] = "moving"
            activity["segments"][0].update(seconds=2000, terrain_factor=2, rest_seconds=300)
            activity["segments"][1].update(seconds=1000)
        result = self.module.compare(data, [{"fatigue_half_slowdown": 0}])
        self.assertEqual(result["candidates"][0]["train"]["mean_segment_wape"], 0)
        self.assertEqual(result["candidates"][0]["train"]["mean_checkpoint_mae_seconds"], 0)

    def test_large_known_rests_do_not_hide_later_checkpoint_errors(self):
        data = self.observations()
        for activity in data["activities"]:
            activity["time_basis"] = "moving"
            activity["segments"] = [
                {"distance_km": 1, "ascent_m": 0, "seconds": seconds}
                for seconds in (1000, 1000, 1160)
            ]
        expected = self.module.compare(data, [{"fatigue_half_slowdown": 0}])["candidates"][0]
        for activity in data["activities"]:
            activity["segments"][0]["rest_seconds"] = 1e20
        actual = self.module.compare(data, [{"fatigue_half_slowdown": 0}])["candidates"][0]
        self.assertEqual(actual, expected)

    def test_wape_normalizes_before_summing_large_finite_errors(self):
        data = self.observations()
        for activity in data["activities"]:
            activity["segments"] = [
                {"distance_km": 1, "ascent_m": 0, "seconds": 1e308},
                {"distance_km": 10, "ascent_m": 0, "seconds": 1e307},
            ]
        report = self.module.compare(data, [{"fatigue_half_slowdown": 0}])
        self.assertAlmostEqual(report["candidates"][0]["train"]["mean_segment_wape"], 18 / 11)
        json.dumps(report, allow_nan=False)

    def test_rejects_leakage_invalid_measurements_and_missing_holdout(self):
        original = self.observations()
        invalid = []
        data = copy.deepcopy(original)
        data["activities"][1]["id"] = "train-1"
        invalid.append(data)
        data = copy.deepcopy(original)
        data["activities"][1]["split"] = "train"
        invalid.append(data)
        for field, value in (("seconds", 0), ("seconds", float("nan")), ("rest_seconds", -1),
                             ("distance_km", True), ("ascent_m", -1), ("terrain_factor", .5)):
            data = copy.deepcopy(original)
            data["activities"][0]["segments"][0][field] = value
            invalid.append(data)
        data = copy.deepcopy(original)
        data["activities"][1]["segments"][0]["rest_seconds"] = 100
        invalid.append(data)
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.module.compare(data, [{"fatigue_half_slowdown": 0}])
        for candidates in ([], [{"typo": .1}], [{"fatigue_model": "linear", "fatigue_rate": .08}]):
            with self.assertRaises(ValueError):
                self.module.compare(original, candidates)

    def test_cli_reports_metrics_without_exporting_raw_activity_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "observations.json"
            path.write_text(json.dumps(self.observations()))
            result = subprocess.run([sys.executable, str(EVAL), "--observations", str(path)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertIn("selected_index", report)
            self.assertNotIn("train-1", result.stdout)


if __name__ == "__main__":
    unittest.main()
