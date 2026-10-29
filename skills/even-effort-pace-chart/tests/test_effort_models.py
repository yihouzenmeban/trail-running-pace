import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pace_chart as pace


class EffortModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "course.gpx"
        self.write_route()

    def write_route(self, uphill=False):
        points = "".join(
            f'<trkpt lat="0" lon="{math.degrees(km * 1000 / 6371008.8)}">'
            f"<ele>{km * 10 if uphill else 0}</ele></trkpt>"
            for km in range(101)
        )
        self.path.write_text(f"<gpx><trk><trkseg>{points}</trkseg></trk></gpx>")

    def plan(self, distances=(1, 10, 50, 90, 100), **options):
        return pace.build_plan(self.path, {
            "targets": ["10:00"],
            "checkpoints": [{"name": f"CP{km}", "distance_km": km} for km in distances],
            **options,
        })

    def test_default_has_finite_start_pace_and_preserves_half_time_ratio(self):
        plan = self.plan(distances=(.0001, .1, 1, 10, 50, 90, 100))
        self.assertEqual(plan["parameters"]["fatigue_model"], "linear")
        self.assertEqual(plan["parameters"]["fatigue_half_slowdown"], .16)
        times = plan["schedules"][0]["checkpoints"]
        paces = [t["eq_pace_seconds_per_km"] for t in times[1:]]
        self.assertGreater(paces[0], 300)
        self.assertLess(paces[0], 360)
        self.assertAlmostEqual(paces[0], paces[1], delta=.1)
        self.assertEqual(paces, sorted(paces))
        halfway = times[5]["arrival_seconds"]
        self.assertAlmostEqual((36000 - halfway) / halfway, 1.16)
        self.assertAlmostEqual(times[-1]["arrival_seconds"], 36000)

    def test_linear_zero_and_explicit_legacy_migration(self):
        plan = self.plan(fatigue_half_slowdown=0)
        for cp, timing in zip(plan["checkpoints"], plan["schedules"][0]["checkpoints"]):
            self.assertAlmostEqual(timing["arrival_seconds"], cp["distance_m"] / 100000 * 36000,
                                   delta=1e-6)
        legacy = self.plan(fatigue_rate=.08)
        explicit = self.plan(fatigue_model="legacy_power", fatigue_rate=.08)
        self.assertEqual(legacy["schedules"], explicit["schedules"])
        self.assertEqual(legacy["parameters"]["fatigue_model"], "legacy_power")
        self.assertIsNone(legacy["parameters"]["fatigue_half_slowdown"])
        self.assertTrue(any("legacy_power" in warning for warning in legacy["warnings"]))
        self.assertAlmostEqual(legacy["schedules"][0]["checkpoints"][1]["arrival_seconds"],
                               36000 * .01 ** pace.fatigue_exponent(.08))

    def test_invalid_or_conflicting_model_options(self):
        for options in (
            {"fatigue_model": "unknown"}, {"fatigue_model": None},
            {"fatigue_half_slowdown": None}, {"fatigue_half_slowdown": True},
            {"fatigue_half_slowdown": -.01}, {"fatigue_half_slowdown": 1.01},
            {"fatigue_model": "linear", "fatigue_rate": .08},
            {"fatigue_model": "legacy_power", "fatigue_half_slowdown": .16},
            {"fatigue_half_slowdown": .16, "fatigue_rate": .08},
        ):
            with self.subTest(options=options), self.assertRaises(pace.InputError):
                self.plan(**options)

    def test_terrain_weights_only_time_not_base_equivalent_distance_or_water(self):
        plan = self.plan(distances=(50, 100), fatigue_half_slowdown=0,
                         terrain_sections=[{"start_km": 0, "end_km": 50, "factor": 2}])
        cps, times = plan["checkpoints"], plan["schedules"][0]["checkpoints"]
        self.assertAlmostEqual(cps[1]["eq_distance_km"], 50)
        self.assertAlmostEqual(cps[1]["effort_distance_km"], 100)
        self.assertAlmostEqual(plan["route"]["eq_distance_km"], 100)
        self.assertAlmostEqual(plan["route"]["effort_distance_km"], 150)
        self.assertAlmostEqual(cps[0]["water_ml"], 3500)
        self.assertAlmostEqual(times[1]["arrival_seconds"], 24000)
        self.assertAlmostEqual(times[2]["arrival_seconds"], 36000)
        self.assertAlmostEqual(times[1]["eq_pace_seconds_per_km"], 480)
        self.assertIn("effort_distance_km", pace.csv_text(plan).splitlines()[0])

    def test_checkpoint_insertion_does_not_change_terrain_fatigue_or_rests(self):
        self.write_route(uphill=True)
        options = {"terrain_sections": [
            {"start_km": 3, "end_km": 37, "factor": 1.4},
            {"start_km": 37, "end_km": 63, "factor": 1.2},
        ]}
        for model in ({"fatigue_half_slowdown": .16}, {"fatigue_rate": .08}):
            sparse = self.plan(distances=(25, 50, 100), **options, **model)
            dense = self.plan(distances=(1, 25, 37, 50, 63, 90, 100), **options, **model)
            original = {cp["name"]: t for cp, t in zip(sparse["checkpoints"],
                                                       sparse["schedules"][0]["checkpoints"])}
            for cp, timing in zip(dense["checkpoints"], dense["schedules"][0]["checkpoints"]):
                if cp["name"] in original:
                    self.assertAlmostEqual(timing["arrival_seconds"], original[cp["name"]]["arrival_seconds"])
            self.assertAlmostEqual(sum(cp["effort_distance_km"] for cp in dense["checkpoints"]),
                                   sparse["route"]["effort_distance_km"])
        rest = self.plan(
            terrain_sections=options["terrain_sections"],
            checkpoints=[{"name": "CP", "distance_km": 50, "rest_minutes": 30},
                         {"name": "Finish", "distance_km": 100}],
        )
        times = rest["schedules"][0]["checkpoints"]
        self.assertAlmostEqual(times[1]["departure_seconds"] - times[1]["arrival_seconds"], 1800)
        self.assertAlmostEqual(sum(t["moving_seconds"] for t in times) + 1800, 36000)

    def test_terrain_validation_and_neutral_factor(self):
        base = self.plan()
        neutral = self.plan(terrain_sections=[{"start_km": 10, "end_km": 20, "factor": 1}])
        self.assertEqual(base["schedules"], neutral["schedules"])
        for sections in (
            None, {}, [{"start_km": 0, "end_km": 101, "factor": 1.1}],
            [{"start_km": 10, "end_km": 5, "factor": 1.1}],
            [{"start_km": 0, "end_km": 5, "factor": .9}],
            [{"start_km": 0, "end_km": 5, "factor": True}],
            [{"start_km": 0, "end_km": 5, "factor": float("inf")}],
            [{"start_km": 0, "end_km": 5, "factor": 1.1, "typo": 0}],
            [{"start_km": 0, "end_km": 10, "factor": 1.1},
             {"start_km": 9, "end_km": 20, "factor": 1.2}],
        ):
            with self.subTest(sections=sections), self.assertRaises(pace.InputError):
                self.plan(terrain_sections=sections)


if __name__ == "__main__":
    unittest.main()
