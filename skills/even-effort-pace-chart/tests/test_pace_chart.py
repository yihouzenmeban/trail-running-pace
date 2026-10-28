import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pace_chart.py"
sys.path.insert(0, str(SCRIPT.parent))
import pace_chart as pace


def gpx(points, waypoints=(), namespace="http://www.topografix.com/GPX/1/1"):
    def point(tag, values):
        lat, lon, elevation, *name = values
        ele = "" if elevation is None else f"<ele>{elevation}</ele>"
        label = "" if not name else f"<name>{name[0]}</name>"
        return f'<{tag} lat="{lat}" lon="{lon}">{ele}{label}</{tag}>'

    wpts = "".join(point("wpt", p) for p in waypoints)
    trk = "".join(point("trkpt", p) for p in points)
    return f'<gpx version="1.1" xmlns="{namespace}">{wpts}<trk><trkseg>{trk}</trkseg></trk></gpx>'


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "course.gpx"
        self.points = [(0, 0, 0), (0, 0.01, 100), (0, 0.02, 0)]

    def write(self, points=None, waypoints=None, **kwargs):
        self.path.write_text(
            gpx(
                self.points if points is None else points,
                [(0, 0.01, None, "CP1")] if waypoints is None else waypoints,
                **kwargs,
            ),
            encoding="utf-8",
        )
        return self.path

    def plan(self, **config):
        return pace.build_plan(self.path, {"target": "04:00", **config})


class GeometryTests(Fixture):
    def test_gain_smoothing_is_independent_from_detailed_profile_and_carries_across_cps(self):
        points = [(0, i * 0.000045, 100 + (2 if i % 2 else -2)) for i in range(81)]
        self.write(points=points, waypoints=[(0, 0.0018, None, "CP1")])
        detailed = self.plan(ascent_smoothing_m=20)
        filtered = self.plan(ascent_smoothing_m=100)
        self.assertLess(filtered["route"]["ascent_m"], detailed["route"]["ascent_m"] / 2)
        self.assertEqual(filtered["checkpoints"][1]["profile"], detailed["checkpoints"][1]["profile"])
        self.assertEqual(filtered["route"]["grade_fractions"], detailed["route"]["grade_fractions"])
        self.assertAlmostEqual(sum(cp["ascent_m"] for cp in filtered["checkpoints"]),
                               filtered["route"]["ascent_m"])
        self.assertAlmostEqual(sum(cp["descent_m"] for cp in filtered["checkpoints"]),
                               filtered["route"]["descent_m"])
        self.assertEqual(filtered["parameters"]["ascent_smoothing_m"], 100)

    def test_gain_filter_preserves_long_climbs_and_visible_small_hill(self):
        points = [(0, i * 0.000045, i * 0.2) for i in range(401)]
        self.write(points=points, waypoints=[(0, 0.009, None, "CP1")])
        plan = self.plan()
        self.assertGreater(plan["route"]["ascent_m"], 77)
        self.assertAlmostEqual(plan["route"]["descent_m"], 0)
        self.write(points=[(0, i * 0.000045, 8 if i == 40 else 0) for i in range(81)],
                   waypoints=[(0, 0.0018, None, "CP1")])
        plan = self.plan()
        elevations = [p[1] for cp in plan["checkpoints"] for p in cp["profile"]]
        self.assertGreater(max(elevations), 1)
        self.assertGreater(plan["route"]["ascent_m"], 0)

    def test_distance_namespace_and_duplicate_coordinates(self):
        for ns in ("", "http://www.topografix.com/GPX/1/0", "http://www.topografix.com/GPX/1/1"):
            self.write(points=[self.points[0], self.points[0], *self.points[1:]], namespace=ns)
            route = pace.load_route(self.path)
            self.assertAlmostEqual(route.total_m, 2223.90, delta=0.1)
            self.assertEqual(len(route.points), 3)

    def test_missing_elevation_and_invalid_coordinates(self):
        for points in (
            [(0, 0, 0), (0, 0.01, None)],
            [(0, 0, 0), (91, 0.01, 0)],
            [(0, 0, 0), (0, float("nan"), 0)],
        ):
            self.write(points=points)
            with self.assertRaises(pace.InputError):
                pace.load_route(self.path)

    def test_multiple_routes_require_selection(self):
        self.write()
        xml = self.path.read_text()
        track = xml[xml.index("<trk>"):xml.index("</trk>") + 6]
        self.path.write_text(xml.replace("</gpx>", track + "</gpx>"))
        with self.assertRaisesRegex(pace.InputError, "track_index"):
            pace.load_route(self.path)
        self.assertGreater(pace.load_route(self.path, track_index=2).total_m, 0)

    def test_disconnected_segments_are_not_joined(self):
        self.write()
        self.path.write_text(
            self.path.read_text().replace(
                '</trkseg>', '</trkseg><trkseg><trkpt lat="1" lon="1"><ele>0</ele></trkpt></trkseg>'
            )
        )
        with self.assertRaisesRegex(pace.InputError, "segment"):
            pace.load_route(self.path)

    def test_route_points_and_embedded_cp(self):
        self.write(points=[(*p, "CP1") if i == 1 else p for i, p in enumerate(self.points)], waypoints=[])
        self.path.write_text(
            self.path.read_text().replace("<trk><trkseg>", "<rte>").replace("</trkseg></trk>", "</rte>")
            .replace("trkpt", "rtept")
        )
        plan = self.plan()
        self.assertEqual([p["name"] for p in plan["checkpoints"]], ["起点", "CP1", "终点"])

    def test_five_metre_sampling_and_exact_twenty_metre_window(self):
        route = pace.Route(
            [(0, 0, 0), (0, 0.001, 0)],
            [pace.Sample(0, 0), pace.Sample(10, 10), pace.Sample(20, 0), pace.Sample(40, 0)],
            [],
        )
        profile = pace.smooth_profile(route, 5, 20)
        self.assertEqual([p.distance_m for p in profile], list(range(0, 41, 5)))
        self.assertAlmostEqual(profile[2].elevation_m, 5)
        self.assertAlmostEqual(profile[0].elevation_m, 5)
        self.assertAlmostEqual(profile[-1].elevation_m, 0)
        self.assertGreater(profile[2].elevation_m, profile[4].elevation_m)

    def test_linear_elevation_and_zero_smoothing(self):
        route = pace.Route([], [pace.Sample(0, 0), pace.Sample(100, 100)], [])
        smoothed = pace.smooth_profile(route, 5, 20)
        self.assertAlmostEqual(smoothed[10].elevation_m, 50)
        original = pace.smooth_profile(route, 5, 0)
        self.assertEqual((original[0].elevation_m, original[-1].elevation_m), (0, 100))

    def test_grade_boundaries(self):
        self.assertEqual(
            [pace.grade_bin(value) for value in (-16, -15, -10, -5, 0, 5, 10, 15, 16)],
            [0, 0, 1, 2, 3, 4, 5, 6, 6],
        )


class CheckpointTests(Fixture):
    def test_recognized_cp_excludes_landmarks_and_turns(self):
        self.write(waypoints=[
            (0, 0.015, None, "Right turn"),
            (0, 0.01, None, "CP1 水站"),
            (0, 0.012, None, "Scenic viewpoint"),
        ])
        plan = self.plan()
        self.assertEqual([p["name"] for p in plan["checkpoints"]], ["起点", "CP1 水站", "终点"])
        self.assertEqual(plan["checkpoints"][1]["id"], "wpt:2")

    def test_no_cp_requires_manual_list_and_ambiguous_names_require_confirmation(self):
        self.write(waypoints=[])
        with self.assertRaisesRegex(pace.InputError, "checkpoints"):
            self.plan()
        self.write(waypoints=[(0, 0.01, None, "Hilltop")])
        with self.assertRaisesRegex(pace.InputError, "cp_selection"):
            self.plan()
        self.assertEqual(self.plan(cp_selection=["wpt:1"])["checkpoints"][1]["name"], "Hilltop")

    def test_off_route_requires_explicit_override(self):
        self.write(waypoints=[(0.002, 0.01, None, "CP1")])
        with self.assertRaisesRegex(pace.InputError, "100"):
            self.plan()
        plan = self.plan(checkpoint_overrides={"wpt:1": {"allow_off_route": True}})
        self.assertEqual(plan["checkpoints"][1]["name"], "CP1")
        self.assertTrue(any("off-route" in warning for warning in plan["warnings"]))

    def test_out_and_back_cp_requires_distance_disambiguation(self):
        self.write(points=[(0, 0, 0), (0, 0.01, 100), (0, 0, 0)],
                   waypoints=[(0, 0.005, None, "CP1")])
        with self.assertRaisesRegex(pace.InputError, "ambiguous"):
            self.plan()
        plan = self.plan(checkpoint_overrides={"wpt:1": {"distance_km": 0.556}})
        self.assertAlmostEqual(plan["checkpoints"][1]["distance_m"], 556)

    def test_combined_start_finish_preserves_venue_and_checks_both_endpoints(self):
        for name in ("起终点-古城", "起終點-古城", "Start / Finish - Town"):
            self.write(points=[(0, 0, 0), (0, 0.01, 100), (0, 0, 0)],
                       waypoints=[(0, 0, None, name), (0, 0.01, None, "CP1")])
            plan = self.plan()
            cps = plan["checkpoints"]
            self.assertEqual(len(cps), 3)
            self.assertEqual((cps[0]["name"], cps[-1]["name"]), (name + "（起点）", name + "（终点）"))
            self.assertEqual((cps[0]["id"], cps[-1]["id"]), ("wpt:1:start", "wpt:1:finish"))
            self.assertEqual(cps[0]["distance_m"], 0)
            self.assertEqual(cps[-1]["distance_m"], plan["route"]["distance_m"])
        self.write(waypoints=[(0, 0, None, "起终点-古城")])
        with self.assertRaisesRegex(pace.InputError, "combined start/finish"):
            self.plan()

    def test_manual_distance_mismatch_requires_confirmed_scaling(self):
        self.write(waypoints=[])
        cps = [{"name": "CP1", "distance_km": 1}, {"name": "终点", "distance_km": 2}]
        with self.assertRaisesRegex(pace.InputError, "scale"):
            self.plan(checkpoints=cps)
        plan = self.plan(checkpoints=cps, distance_alignment="scale")
        self.assertAlmostEqual(plan["checkpoints"][1]["distance_m"], plan["route"]["distance_m"] / 2)
        self.assertAlmostEqual(plan["checkpoints"][1]["official_distance_km"], 1)
        self.assertAlmostEqual(plan["route"]["distance_scale"], plan["route"]["distance_m"] / 2000)

    def test_invalid_cp_lists(self):
        self.write()
        for cps in (
            [],
            [{"name": "CP1", "distance_km": -1}],
            [{"name": "CP1", "distance_km": 1}, {"name": "终点", "distance_km": 0.5}],
            [{"name": "终点", "distance_km": 2.2239, "rest_minutes": 5}],
        ):
            with self.assertRaises(pace.InputError):
                self.plan(checkpoints=cps)

    def test_cp_splits_preserve_route_statistics(self):
        self.write()
        plan = self.plan()
        cps = plan["checkpoints"]
        for key, route_key in (("segment_distance_m", "distance_m"), ("ascent_m", "ascent_m"),
                               ("descent_m", "descent_m"), ("eq_distance_km", "eq_distance_km")):
            self.assertAlmostEqual(sum(cp[key] for cp in cps), plan["route"][route_key])
        for cp in cps[1:]:
            self.assertAlmostEqual(sum(cp["grade_fractions"]), 1)


REAL_GPX = SCRIPT.parents[3] / "assets" / "天地留白100K.gpx"


@unittest.skipUnless(REAL_GPX.is_file(), "Optional user-supplied real GPX is not present")
class RealRouteTests(unittest.TestCase):
    def test_real_course_automatic_cps_and_four_outputs(self):
        plan = pace.build_plan(REAL_GPX, {"target": "24:00", "name": "天地留白100K · 示例"})
        self.assertAlmostEqual(plan["route"]["distance_m"], 101248.68, delta=1)
        reference_gains = [397, 394, 439, 666, 893, 583, 531, 403, 567, 233, 220]
        self.assertAlmostEqual(plan["route"]["ascent_m"], sum(reference_gains), delta=100)
        error = sum(abs(cp["ascent_m"] - expected)
                    for cp, expected in zip(plan["checkpoints"][1:], reference_gains))
        self.assertLess(error / len(reference_gains), 20)
        self.assertEqual(len(plan["checkpoints"]), 12)
        self.assertEqual(plan["checkpoints"][0]["name"], "起终点-徽州古城（起点）")
        self.assertEqual(plan["checkpoints"][-1]["name"], "起终点-徽州古城（终点）")
        self.assertEqual(plan["checkpoints"][-3]["name"], "CP12-瞻淇村")
        self.assertEqual(plan["checkpoints"][-2]["name"], "CP13-画家村")
        for schedule in plan["schedules"]:
            self.assertAlmostEqual(schedule["checkpoints"][-1]["departure_seconds"],
                                   schedule["target_seconds"])
            self.assertAlmostEqual(sum(t["moving_seconds"] for t in schedule["checkpoints"]),
                                   schedule["target_seconds"])
        for cp_key, route_key in (("segment_distance_m", "distance_m"), ("ascent_m", "ascent_m"),
                                  ("descent_m", "descent_m"), ("eq_distance_km", "eq_distance_km")):
            self.assertAlmostEqual(sum(cp[cp_key] for cp in plan["checkpoints"]), plan["route"][route_key])
        inspected = pace.inspect_route(REAL_GPX)
        self.assertAlmostEqual(inspected["ascent_m"], plan["route"]["ascent_m"])
        with tempfile.TemporaryDirectory() as output:
            paths = pace.write_outputs(plan, Path(output))
            self.assertEqual(len(paths), 4)
            ET.parse(Path(output) / "pace-chart.svg")
            with (Path(output) / "pace-chart.csv").open(encoding="utf-8-sig", newline="") as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 60)


class TimingTests(Fixture):
    def setUp(self):
        super().setUp()
        self.write(points=[(0, 0, 0), (0, 0.01, 0), (0, 0.02, 0)])

    def test_default_targets_and_custom_step_and_list(self):
        self.assertEqual(self.plan()["targets_seconds"], [10800, 12600, 14400, 16200, 18000])
        self.assertEqual(self.plan(target_step_minutes=15)["targets_seconds"],
                         [12600, 13500, 14400, 15300, 16200])
        self.assertEqual(self.plan(targets=["30:00", "25:30"])["targets_seconds"], [91800, 108000])

    def test_zero_fatigue_linear_and_default_doubling(self):
        plan = self.plan(fatigue_rate=0, targets=["04:00"])
        schedule = plan["schedules"][0]["checkpoints"]
        self.assertAlmostEqual(schedule[1]["arrival_seconds"], 7200)
        self.assertAlmostEqual(schedule[2]["arrival_seconds"], 14400)
        b = pace.fatigue_exponent(0.08)
        self.assertAlmostEqual(2 ** (b - 1), 1.08)
        plan = self.plan(targets=["04:00"])
        times = plan["schedules"][0]["checkpoints"]
        self.assertGreater(times[2]["moving_seconds"], times[1]["moving_seconds"])

    def test_rests_are_included_and_cutoffs_mark_arrival_and_departure(self):
        plan = self.plan(targets=["04:00"], fatigue_rate=0,
                         checkpoint_overrides={"wpt:1": {"rest_minutes": 20, "cutoff": "02:00"}})
        times = plan["schedules"][0]["checkpoints"]
        self.assertAlmostEqual(times[1]["arrival_seconds"], 6600)
        self.assertAlmostEqual(times[1]["departure_seconds"], 7800)
        self.assertEqual(times[1]["cutoff_status"], "departure_late")
        self.assertAlmostEqual(times[-1]["departure_seconds"], 14400)
        self.assertAlmostEqual(sum(t["moving_seconds"] for t in times) + 1200, 14400)
        plan = self.plan(targets=["04:00"], fatigue_rate=0,
                         checkpoint_overrides={"wpt:1": {"cutoff": "01:59"}})
        self.assertEqual(plan["schedules"][0]["checkpoints"][1]["cutoff_status"], "arrival_late")
        plan = self.plan(targets=["04:00"], fatigue_rate=0,
                         checkpoint_overrides={"wpt:1": {"cutoff": "02:00"}})
        self.assertEqual(plan["schedules"][0]["checkpoints"][1]["cutoff_status"], "on_time")

    def test_invalid_targets_and_parameters(self):
        for config in (
            {"target": "00:30"}, {"targets": ["04:00", "04:00"]}, {"targets": []},
            {"target": "04:60"}, {"fatigue_rate": -0.1}, {"sample_m": 0},
            {"smoothing_m": -1}, {"sample_m": float("nan")}, {"typo": 1},
            {"ascent_smoothing_m": -1}, {"start_time": "invalid date"},
            {"targets": ["00:10"], "checkpoint_overrides": {"wpt:1": {"rest_minutes": 20}}},
        ):
            with self.assertRaises(pace.InputError):
                self.plan(**config)

    def test_water_and_extended_time_display(self):
        plan = self.plan(targets=["30:00"])
        self.assertAlmostEqual(sum(p["water_ml"] for p in plan["checkpoints"]),
                               plan["route"]["eq_distance_km"] * 70)
        self.assertEqual(pace.format_duration(91800), "25:30:00")
        self.assertEqual(pace.format_pace(359.6), "6:00")
        cps = plan["checkpoints"]
        self.assertAlmostEqual(cps[0]["water_ml"], cps[1]["eq_distance_km"] * 70)
        self.assertAlmostEqual(cps[1]["water_ml"], cps[2]["eq_distance_km"] * 70)
        self.assertEqual(cps[-1]["water_ml"], 0)

    def test_reference_interval_pace_uses_horizontal_distance_and_can_select_equivalent(self):
        self.write()
        plan = self.plan(targets=["04:00"])
        cp, timing = plan["checkpoints"][1], plan["schedules"][0]["checkpoints"][1]
        expected = timing["moving_seconds"] / (cp["segment_distance_m"] / 1000)
        self.assertAlmostEqual(timing["pace_seconds_per_km"], expected)
        self.assertGreater(timing["pace_seconds_per_km"], timing["eq_pace_seconds_per_km"])
        self.assertEqual(plan["parameters"]["pace_basis"], "distance")
        self.assertIn("括号内：区间配速", pace.render_svg(plan))
        equivalent = self.plan(targets=["04:00"], pace_basis="equivalent")
        alternate = equivalent["schedules"][0]["checkpoints"][1]
        self.assertAlmostEqual(alternate["pace_seconds_per_km"], alternate["eq_pace_seconds_per_km"])
        self.assertIn("括号内：区间等效配速", pace.render_svg(equivalent))
        self.assertEqual(plan["targets_seconds"], equivalent["targets_seconds"])
        self.assertEqual(timing["departure_seconds"], alternate["departure_seconds"])
        with self.assertRaises(pace.InputError):
            self.plan(pace_basis="typo")


class ExportTests(Fixture):
    def setUp(self):
        super().setUp()
        self.write()

    def test_all_formats_share_values_and_svg_is_standalone(self):
        plan = self.plan()
        paths = pace.write_outputs(plan, Path(self.temp.name) / "result")
        self.assertEqual({p.suffix for p in paths}, {".svg", ".html", ".csv", ".json"})
        saved = json.loads(next(p for p in paths if p.suffix == ".json").read_text())
        self.assertEqual(saved, plan)
        svg = next(p for p in paths if p.suffix == ".svg").read_text()
        html = next(p for p in paths if p.suffix == ".html").read_text()
        root = ET.fromstring(svg)
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        for element in root.iter():
            self.assertNotEqual(element.tag.rsplit("}", 1)[-1], "foreignObject")
            self.assertNotIn("href", element.attrib)
        self.assertIn("@page", html)
        self.assertIn("table-header-group", html)
        with next(p for p in paths if p.suffix == ".csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), len(plan["checkpoints"]) * len(plan["schedules"]))
        for schedule in plan["schedules"]:
            for cp, timing in zip(plan["checkpoints"], schedule["checkpoints"]):
                record = next(row for row in rows if row["checkpoint_id"] == cp["id"]
                              and float(row["target_seconds"]) == schedule["target_seconds"])
                self.assertAlmostEqual(float(record["departure_seconds"]), timing["departure_seconds"])
                for output in (html, svg):
                    self.assertIn(pace.format_chart_time(timing["departure_seconds"]), output)
                    if timing["pace_seconds_per_km"] is not None:
                        self.assertIn(pace.format_chart_pace(timing["pace_seconds_per_km"]), output)

    def test_escape_text_and_long_names_many_columns(self):
        name = '赛事 & <script>alert("x")</script>'
        long_name = "超长补给站名称" * 8 + " & <tag>"
        plan = self.plan(name=name, targets=["12:00", "13:00", "14:00", "15:00", "16:00", "17:00"],
                         checkpoint_overrides={"wpt:1": {"name": long_name}})
        svg = pace.render_svg(plan)
        html = pace.render_html(plan)
        root = ET.fromstring(svg)
        self.assertIn(name, "".join(root.itertext()))
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn('<script>alert("x")</script>', html)
        self.assertGreater(float(root.attrib["width"]), 1500)
        self.assertIn("超长补给站名称", "".join(root.itertext()))

    def test_vector_graphics_have_cell_positions_and_missing_cutoffs_are_visible(self):
        plan = self.plan()
        root = ET.fromstring(pace.render_svg(plan))
        ns = {"svg": "http://www.w3.org/2000/svg"}
        graphics = [item for item in root.findall("svg:g", ns) if "transform" in item.attrib]
        self.assertEqual(len(graphics), 2 * len(plan["checkpoints"]))
        # Histogram and profile groups must be placed below the header inside their columns.
        for item in graphics:
            transform = item.attrib["transform"].removeprefix("translate(").removesuffix(")")
            x, y = (float(value) for value in transform.split())
            self.assertGreaterEqual(x, 100)
            self.assertLess(x, 360)
            self.assertGreaterEqual(y, 100)
        self.assertIn("关门 未提供", pace.cp_details(plan["checkpoints"][1]))
        self.assertIn("关门 未提供", pace.render_html(plan))

    def test_reference_table_layout_colours_start_time_and_minute_times(self):
        plan = self.plan(start_time="2026-10-31 06:00", targets=["12:00", "13:00", "14:00", "15:00", "16:00"])
        self.assertEqual([label for label, _ in pace.BASE_COLUMNS],
                         ["累积\n距离", "坡度\n分布", "肖像图", "距离", "爬升", "下降", "水", "位置"])
        for output in (pace.render_svg(plan), pace.render_html(plan)):
            self.assertIn("2026-10-31 06:00", output)
            self.assertIn("Target", output)
            self.assertIn("14.0 Hr", output)
        root = ET.fromstring(pace.render_svg(plan))
        ns = {"svg": "http://www.w3.org/2000/svg"}
        by_column = {}
        for cell in root.findall("svg:rect", ns):
            if "data-column" in cell.attrib:
                by_column.setdefault(cell.attrib["data-column"], set()).add(cell.attrib["fill"])
        for column in ("distance", "ascent", "descent", "water"):
            self.assertTrue(by_column[column] - {"#ffffff"})
        histogram = ET.fromstring(pace.histogram_svg([0.1, 0.1, 0.1, 0.4, 0.1, 0.1, 0.1]))
        bars = histogram.findall("svg:rect", ns)
        self.assertEqual([bar.attrib["fill"] for i, bar in enumerate(bars) if i != 3], ["#111111"] * 6)
        self.assertEqual(bars[3].attrib["fill"], "#ffffff")
        self.assertEqual(pace.format_chart_time(25 * 3600 + 59), "25:00")
        self.assertEqual(pace.format_chart_pace(359.6), "06:00")

    def test_csv_formula_names_and_overwrite_protection(self):
        plan = self.plan(checkpoint_overrides={"wpt:1": {"name": "=SUM(1,2)"}})
        output = Path(self.temp.name) / "out"
        paths = pace.write_outputs(plan, output)
        csv_path = next(p for p in paths if p.suffix == ".csv")
        with csv_path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertTrue(any(row["checkpoint_name"] == "'=SUM(1,2)" for row in rows))
        with self.assertRaises(pace.InputError):
            pace.write_outputs(plan, output)
        pace.write_outputs(plan, output, overwrite=True)

    def test_cli_inspect_generate_and_actionable_error(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "inspect", str(self.path)],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["cp_candidates"][0]["name"], "CP1")
        config = Path(self.temp.name) / "race.json"
        config.write_text(json.dumps({"target": "04:00"}))
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "generate", str(self.path), "--config", str(config),
             "--output-dir", str(Path(self.temp.name) / "cli")], text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)["outputs"]), 4)
        self.write(waypoints=[])
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "generate", str(self.path), "--config", str(config),
             "--output-dir", str(Path(self.temp.name) / "error")], text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("checkpoints", json.loads(result.stderr)["error"])
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
