import importlib.util
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET


spec = importlib.util.spec_from_file_location(
    "mgw_comparison", Path(__file__).with_name("comparison.py")
)
comparison = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = comparison
spec.loader.exec_module(comparison)


class ElevationRepairTests(unittest.TestCase):
    def test_fills_by_distance_and_preserves_original_fields(self):
        root = ET.fromstring(
            '<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>'
            '<trkpt lat="0" lon="0"><ele>100</ele><time>a</time></trkpt>'
            '<trkpt lat="0" lon="0.001"><time>b</time></trkpt>'
            '<trkpt lat="0" lon="0.004"><ele>140</ele><time>c</time></trkpt>'
            '</trkseg></trk></gpx>'
        )
        report = comparison.fill_elevations(root)
        points = root.findall(".//{*}trkpt")
        self.assertEqual(report["missing_points"], 1)
        self.assertAlmostEqual(float(points[1].findtext("{*}ele")), 110)
        self.assertEqual(points[0].findtext("{*}ele"), "100")
        self.assertEqual(points[2].findtext("{*}ele"), "140")
        self.assertEqual([p.findtext("{*}time") for p in points], ["a", "b", "c"])
        self.assertEqual(points[1].attrib, {"lat": "0", "lon": "0.001"})

    def test_does_not_extrapolate_missing_endpoint(self):
        root = ET.fromstring(
            '<gpx><trk><trkseg><trkpt lat="0" lon="0"/>'
            '<trkpt lat="0" lon="0.001"><ele>100</ele></trkpt>'
            '</trkseg></trk></gpx>'
        )
        with self.assertRaisesRegex(ValueError, "endpoint"):
            comparison.fill_elevations(root)


class ComparisonDataTests(unittest.TestCase):
    def test_minute_difference_matches_chart_display(self):
        self.assertEqual(comparison.chart_minutes(3599.99), 59)
        self.assertEqual(comparison.chart_minutes(3600), 60)
        self.assertEqual(comparison.parse_minutes("12:30"), 750)
        with self.assertRaises(ValueError):
            comparison.parse_minutes("06:60")

    def test_lap_estimates_are_additive_at_boundaries(self):
        laps = [
            {"distance_m": 1000, "ascent_m": 20, "descent_m": 10},
            {"distance_m": 2000, "ascent_m": 40, "descent_m": 30},
        ]
        self.assertEqual(comparison.lap_estimate(laps, 0, "ascent_m"), 0)
        self.assertEqual(comparison.lap_estimate(laps, 1000, "ascent_m"), 20)
        self.assertEqual(comparison.lap_estimate(laps, 2000, "ascent_m"), 40)
        self.assertEqual(comparison.lap_estimate(laps, 1500, "ascent_m"), 30)
        self.assertIsNone(comparison.lap_estimate(laps, 2500, "ascent_m"))
        self.assertIsNone(comparison.lap_estimate([], 1000, "ascent_m"))

    def test_missing_lap_ascent_is_not_treated_as_zero(self):
        laps = [
            {"distance_m": 1000, "ascent_m": None},
            {"distance_m": 2000, "ascent_m": None},
        ]
        self.assertIsNone(comparison.lap_estimate(laps, 1500, "ascent_m"))

    def test_station_uses_recorded_distance_and_elapsed_time(self):
        records = [
            {"lat": 0, "lon": 0, "distance_m": 0, "elapsed_seconds": 0},
            {"lat": 0, "lon": 0.001, "distance_m": 200, "elapsed_seconds": 100},
            {"lat": 0, "lon": 0.002, "distance_m": 400, "elapsed_seconds": 220},
        ]
        matches = comparison.match_checkpoints(
            records, [{"name": "M1", "lat": 0, "lon": 0.0005}]
        )
        self.assertAlmostEqual(matches[0]["distance_m"], 100)
        self.assertAlmostEqual(matches[0]["elapsed_seconds"], 50)
        self.assertLess(matches[0]["offset_m"], 0.01)

    def test_station_match_rejects_far_or_reverse_order(self):
        records = [
            {"lat": 0, "lon": 0, "distance_m": 0, "elapsed_seconds": 0},
            {"lat": 0, "lon": 0.001, "distance_m": 100, "elapsed_seconds": 60},
            {"lat": 0, "lon": 0.002, "distance_m": 200, "elapsed_seconds": 120},
        ]
        for stations in (
            [{"name": "M1", "lat": 1, "lon": 1}],
            [{"name": "M1", "lat": 0, "lon": 0.0015},
             {"name": "M2", "lat": 0, "lon": 0.0005}],
        ):
            with self.subTest(stations=stations), self.assertRaises(ValueError):
                comparison.match_checkpoints(records, stations)

    def test_example_data_has_sixteen_targets_and_matching_stations(self):
        data = comparison.build_data()
        self.assertEqual(data["targets_hours"], [5 + i / 2 for i in range(16)])
        self.assertEqual(len(data["local"]["checkpoints"]), 7)
        for row, cp in enumerate(data["local"]["checkpoints"]):
            self.assertEqual(len(cp["elapsed_minutes"]), 16)
            for col in range(16):
                source = data["reference"]["checkpoints"][row]["elapsed"][col]
                self.assertEqual(
                    cp["delta_minutes"][col],
                    cp["elapsed_minutes"][col] - comparison.parse_minutes(source),
                )
        self.assertEqual(data["parameters"]["start_time"], "06:00")
        self.assertEqual(data["parameters"]["secondary_display"], "pace")
        self.assertEqual(data["parameters"]["output_formats"], ["svg"])
        self.assertEqual(data["local"]["checkpoints"][-1]["elapsed_minutes"],
                         list(range(300, 751, 30)))


if __name__ == "__main__":
    unittest.main()
