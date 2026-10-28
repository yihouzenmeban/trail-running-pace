import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


EVALS = Path(__file__).resolve().parents[1] / "evals"
sys.path.insert(0, str(EVALS))
import evaluate


class BehaviorCheckerTests(unittest.TestCase):
    def test_accepts_valid_candidate_configurations(self):
        candidates = {
            "target_only": {"target": "05:00"},
            "start_does_not_select_arrival": {
                "target": "05:00", "start_time": "06:00", "target_step_minutes": 30,
            },
            "explicit_arrival": {"target": "05:00", "secondary_display": "arrival_time"},
            "replace_target_list": {"target": "05:00", "start_time": "07:30", "fatigue_rate": 0.1},
            "preserve_zero_false": {
                "target": "05:00", "smoothing_m": 0, "fatigue_rate": 0,
                "water_ml_per_10km": 0, "use_kml_altitudes": False,
            },
        }
        self.assertEqual(set(candidates), {case["id"] for case in evaluate.SUITE["cases"]})
        for case_id, config in candidates.items():
            with self.subTest(case=case_id):
                result = evaluate.evaluate(case_id, config)
                self.assertTrue(result["passed"], result["errors"])

    def test_rejects_unrequested_display_exports_and_other_parameter_changes(self):
        for override in (
            {"secondary_display": "arrival_time"}, {"output_formats": ["svg", "json"]},
            {"sample_m": 25}, {"fatigue_rate": 0},
            {"checkpoint_overrides": {"wpt:1": {"rest_minutes": 10}}},
            {"checkpoint_overrides": {"wpt:1": {"cutoff": "04:00"}}},
            {"cp_selection": []},
        ):
            with self.subTest(override=override):
                self.assertFalse(evaluate.evaluate("target_only", {"target": "05:00", **override})["passed"])

    def test_rejects_stale_target_list_even_when_new_target_is_present(self):
        result = evaluate.evaluate("replace_target_list", {
            "target": "05:00", "targets": ["12:00", "13:00"],
            "start_time": "07:30", "fatigue_rate": 0.1,
        })
        self.assertFalse(result["passed"])
        self.assertTrue(any("targets_seconds" in error for error in result["errors"]))

    def test_reports_invalid_candidate_as_failure(self):
        for config in ({}, {"target": "05:00", "unknown_option": True}, []):
            self.assertFalse(evaluate.evaluate("target_only", config)["passed"])

    def test_checker_cli_reports_pass_and_fail_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            for target, code in (("05:00", 0), ("06:00", 1)):
                path.write_text(json.dumps({"target": target}))
                result = subprocess.run([
                    sys.executable, str(EVALS / "evaluate.py"), "--case", "target_only",
                    "--config", str(path),
                ], capture_output=True, text=True)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual(json.loads(result.stdout)["passed"], code == 0)
