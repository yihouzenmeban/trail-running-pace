import copy
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import activity_data as data
import compare_activity as compare
import pace_chart as pace


def messages():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return {
        "session_mesgs": [{
            "start_time": start, "total_distance": 4000,
            "total_elapsed_time": 4000, "total_timer_time": 3900,
            "total_ascent": 44, "total_descent": 24,
        }],
        "record_mesgs": [
            {"timestamp": start + timedelta(seconds=i * 1000),
             "position_lat": round(30 * 2**31 / 180),
             "position_long": round((110 + i * .01) * 2**31 / 180),
             "distance": i * 1000}
            for i in range(5)
        ],
        "lap_mesgs": [
            {"start_time": start + timedelta(seconds=i * 2000),
             "total_distance": 2000, "total_ascent": 20 + i * 4,
             "total_descent": 10 + i * 4}
            for i in range(2)
        ],
    }


def route_file(folder, kml=False):
    path = Path(folder) / ("race.kml" if kml else "race.gpx")
    coords = [(30, 110 + i * .01, 100 + i * 20) for i in range(5)]
    if kml:
        path.write_text('<kml><Document><Placemark><LineString><altitudeMode>absolute'
                        '</altitudeMode><coordinates>' +
                        " ".join(f"{lon},{lat},{z}" for lat, lon, z in coords) +
                        '</coordinates></LineString></Placemark></Document></kml>')
    else:
        path.write_text('<gpx><wpt lat="30" lon="110.02"><name>CP1</name></wpt>'
                        '<trk><trkseg>' + "".join(
                            f'<trkpt lat="{lat}" lon="{lon}"><ele>{z}</ele></trkpt>'
                            for lat, lon, z in coords) + '</trkseg></trk></gpx>')
    return path


class ActivityDataTests(unittest.TestCase):
    def test_fit_totals_without_platform(self):
        activity = data.activity_from_messages(messages())
        self.assertEqual(activity["totals"]["ascent_m"], 44)
        self.assertEqual(activity["totals_source"], "FIT session")
        self.assertEqual(activity["records"][-1]["elapsed_seconds"], 4000)
        self.assertEqual(data.lap_value(activity["laps"], 1500, "ascent_m"), 15)

    def test_platform_finish_is_not_rescaled(self):
        activity = data.activity_from_messages(messages(), {
            "activityId": 123, "activityName": "Example",
            "summaryDTO": {"distance": 4001, "elapsedDuration": 4001.25,
                           "elevationGain": 45, "elevationLoss": 23},
        })
        self.assertEqual(activity["totals"]["ascent_m"], 45)
        self.assertEqual(data.lap_value(activity["laps"], 2000, "ascent_m"), 20)
        self.assertTrue(activity["warnings"])

    def test_missing_lap_metrics_propagate_unknown(self):
        raw = messages()
        del raw["lap_mesgs"][0]["total_ascent"]
        activity = data.activity_from_messages(raw)
        self.assertIsNone(data.lap_value(activity["laps"], 500, "ascent_m"))
        self.assertIsNone(data.lap_value(activity["laps"], 3000, "ascent_m"))
        self.assertEqual(data.lap_value(activity["laps"], 3000, "descent_m"), 17)

    def test_no_laps_is_valid_but_unknown_between_checkpoints(self):
        raw = messages()
        raw["lap_mesgs"] = []
        activity = data.activity_from_messages(raw)
        self.assertIsNone(data.lap_value(activity["laps"], 2000, "ascent_m"))

    def test_bad_sessions_and_record_order_are_rejected(self):
        for field, value in [
            ("session_mesgs", []),
            ("session_mesgs", messages()["session_mesgs"] * 2),
            ("record_mesgs", list(reversed(messages()["record_mesgs"]))),
        ]:
            raw = messages()
            raw[field] = value
            with self.subTest(field=field), self.assertRaises(pace.InputError):
                data.activity_from_messages(raw)

    def test_missing_records_are_reported_and_invalid_values_rejected(self):
        raw = messages()
        raw["record_mesgs"].insert(1, {"timestamp": raw["session_mesgs"][0]["start_time"]})
        self.assertEqual(data.activity_from_messages(raw)["skipped_records"], 1)
        raw["record_mesgs"][2]["distance"] = float("nan")
        with self.assertRaises(pace.InputError):
            data.activity_from_messages(raw)

    def test_invalid_laps_disable_estimation_instead_of_shifting_boundaries(self):
        raw = messages()
        del raw["lap_mesgs"][0]["total_distance"]
        activity = data.activity_from_messages(raw)
        self.assertEqual(activity["laps"], [])
        self.assertTrue(activity["warnings"])

    def test_direct_and_zipped_fit_and_decoder_failures(self):
        with tempfile.TemporaryDirectory() as folder:
            direct = Path(folder) / "activity.fit"
            direct.write_bytes(b"synthetic FIT")
            zipped = Path(folder) / "activity.zip"
            with ZipFile(zipped, "w") as archive:
                archive.writestr("nested/activity.fit", direct.read_bytes())
            with patch.object(data, "decode_fit", return_value=messages()) as decoder:
                self.assertEqual(data.read_activity(direct)["totals"]["distance_m"], 4000)
                self.assertEqual(data.read_activity(zipped)["totals"]["distance_m"], 4000)
                self.assertEqual(decoder.call_count, 2)
            with ZipFile(zipped, "a") as archive:
                archive.writestr("other.fit", b"other")
            with self.assertRaisesRegex(pace.InputError, "one FIT"):
                data.read_activity(zipped)
            zipped.write_bytes(b"broken zip")
            with self.assertRaises(pace.InputError):
                data.read_activity(zipped)
            with patch.object(data, "decode_fit", side_effect=pace.InputError("Damaged FIT")):
                with self.assertRaisesRegex(pace.InputError, "Damaged"):
                    data.read_activity(direct)


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = route_file(self.folder.name)
        self.config = {"targets": ["01:00", "02:00"]}
        self.plan, self.route = compare.load_plan(self.path, self.config)
        self.activity = data.activity_from_messages(messages())

    def build(self, **kwargs):
        return compare.build_comparison(self.plan, self.route, self.activity, **kwargs)

    def test_segment_sums_and_signs(self):
        result = self.build()
        segments = result["segments"]
        self.assertEqual(len(segments), 2)
        self.assertAlmostEqual(sum(s["actual_seconds"] for s in segments), 4000)
        for j, target in enumerate((3600, 7200)):
            self.assertAlmostEqual(sum(s["plans"][j]["seconds"] for s in segments), target)
            for s in segments:
                self.assertAlmostEqual(s["plans"][j]["delta_seconds"],
                                       s["plans"][j]["seconds"] - s["actual_seconds"])
        self.assertAlmostEqual(result["checkpoints"][1]["ascent_m"], 20, places=3)
        self.assertAlmostEqual(result["terrain"][1]["actual_ascent_m"], 24, places=3)

    def test_rest_is_in_following_leg(self):
        self.config["checkpoint_overrides"] = {"wpt:1": {"rest_minutes": 5}}
        plan, route = compare.load_plan(self.path, self.config)
        result = compare.build_comparison(plan, route, self.activity)
        timing = plan["schedules"][0]["checkpoints"]
        self.assertAlmostEqual(result["segments"][1]["plans"][0]["seconds"],
                               timing[2]["moving_seconds"] + 300)

    def test_targets_override_without_mutating_config(self):
        original = copy.deepcopy(self.config)
        plan, _ = compare.load_plan(self.path, self.config, ["26:00"])
        self.assertEqual(plan["targets_seconds"], [93600])
        self.assertEqual(self.config, original)
        self.assertEqual(compare.clock(93600.5), "26:00:01")
        self.assertEqual(compare.time_delta(-.5), "-00:00:01")
        self.assertEqual(compare.time_delta(.1), "00:00:00")

    def test_manual_kml_positions_and_exact_target_list(self):
        path = route_file(self.folder.name, kml=True)
        total = pace.load_route(path).total_m
        plan, route = compare.load_plan(path, {
            "targets": ["01:00"], "checkpoints": [
                {"name": "Aid", "distance_km": total / 2000},
                {"name": "Finish", "distance_km": total / 1000},
            ],
        })
        result = compare.build_comparison(plan, route, self.activity)
        self.assertEqual(result["checkpoints"][1]["id"], "manual:1")
        self.assertAlmostEqual(result["checkpoints"][1]["elapsed_seconds"], 2000, places=2)

    def test_off_route_and_time_override(self):
        self.route.candidates[0]["lat"] += .01
        with self.assertRaisesRegex(pace.InputError, "100 m"):
            self.build()
        result = self.build(overrides={"wpt:1": "00:30"})
        self.assertEqual(result["checkpoints"][1]["elapsed_seconds"], 1800)
        self.assertEqual(result["checkpoints"][1]["match_method"], "elapsed override")
        self.assertTrue(result["warnings"])
        with self.assertRaisesRegex(pace.InputError, "Unknown"):
            self.build(overrides={"typo": "00:30"})
        with self.assertRaises(pace.InputError):
            self.build(overrides={"wpt:1": "02:00"})

    def test_repeated_route_occurrences_require_confirmation(self):
        activity = copy.deepcopy(self.activity)
        records = activity["records"]
        activity["records"] = records + [
            {**r, "elapsed_seconds": r["elapsed_seconds"] + 5000,
             "distance_m": r["distance_m"] + 5000} for r in records
        ]
        activity["totals"]["elapsed_seconds"] = 9000
        activity["totals"]["distance_m"] = 9000
        with self.assertRaisesRegex(pace.InputError, "ambiguous"):
            compare.build_comparison(self.plan, self.route, activity)
        result = compare.build_comparison(self.plan, self.route, activity,
                                          {"wpt:1": "00:33:20"})
        self.assertEqual(result["checkpoints"][1]["elapsed_seconds"], 2000)

    def test_stationary_passage_and_precise_numeric_override(self):
        activity = copy.deepcopy(self.activity)
        stationary = activity["records"][2]
        activity["records"].insert(3, {**stationary, "elapsed_seconds": 2200})
        with self.assertRaisesRegex(pace.InputError, "stationary"):
            compare.build_comparison(self.plan, self.route, activity)
        result = compare.build_comparison(self.plan, self.route, activity, {"wpt:1": 2000.25})
        self.assertEqual(result["checkpoints"][1]["elapsed_seconds"], 2000.25)
        self.assertEqual(result["passage_overrides"], {"wpt:1": 2000.25})
        for invalid in ([], {"wpt:1": True}, {"wpt:1": float("nan")}):
            with self.subTest(invalid=invalid), self.assertRaises(pace.InputError):
                compare.build_comparison(self.plan, self.route, activity, invalid)

    def test_processed_distance_override_is_authoritative(self):
        self.config["checkpoint_overrides"] = {"wpt:1": {"distance_km": self.route.total_m / 4000}}
        plan, route = compare.load_plan(self.path, self.config)
        result = compare.build_comparison(plan, route, self.activity)
        self.assertAlmostEqual(result["checkpoints"][1]["elapsed_seconds"], 1000, places=2)

    def test_reversed_station_order_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["checkpoints"].insert(2, {**plan["checkpoints"][1], "id": "extra", "distance_m": 100})
        with self.assertRaises(pace.InputError):
            compare.build_comparison(plan, self.route, self.activity)

    def test_missing_terrain_stays_unknown(self):
        self.activity["laps"] = []
        result = self.build()
        self.assertIsNone(result["terrain"][0]["actual_ascent_m"])
        self.assertIsNone(result["terrain"][1]["actual_ascent_m"])

    def test_time_charts_pair_cumulative_curves_and_segment_bars(self):
        import xml.etree.ElementTree as ET
        from comparison_svg import render_svg, time_status
        result = self.build()
        root = ET.fromstring(render_svg(result))
        panels = root.findall(".//{*}g[@class='target-panel']")
        self.assertEqual(len(panels), len(self.plan["schedules"]))
        scales = {"cumulative": set(), "segment": set()}
        for panel, schedule in zip(panels, self.plan["schedules"]):
            cumulative = panel.find("{*}g[@data-kind='cumulative']")
            segment_plot = panel.find("{*}g[@data-kind='segment']")
            self.assertGreater(float(segment_plot.get("data-y-top")), float(cumulative.get("data-y-bottom")))
            self.assertEqual(segment_plot.get("data-x-min"), cumulative.get("data-x-min"))
            self.assertEqual(segment_plot.get("data-x-max"), cumulative.get("data-x-max"))
            for kind, plot in (("cumulative", cumulative), ("segment", segment_plot)):
                scales[kind].add(plot.get("data-limit-seconds"))
                self.assertIsNotNone(plot.find("{*}path[@data-role='zero-line']"))
            points = cumulative.findall(".//{*}circle[@data-delta-seconds]")
            self.assertEqual(len(points), len(result["checkpoints"]))
            zero = float(cumulative.get("data-zero-y"))
            scale = float(cumulative.get("data-pixels-per-second"))
            x0, x1 = float(cumulative.get("data-x-min")), float(cumulative.get("data-x-max"))
            for cp, actual, predicted, point in zip(self.plan["checkpoints"], result["checkpoints"], schedule["checkpoints"], points):
                delta = predicted["arrival_seconds"] - actual["elapsed_seconds"]
                self.assertAlmostEqual(float(point.get("data-delta-seconds")), delta)
                self.assertAlmostEqual(float(point.get("cx")), x0 + cp["distance_m"] /
                                       self.plan["route"]["distance_m"] * (x1 - x0), places=2)
                self.assertAlmostEqual(float(point.get("cy")), zero - delta * scale, places=2)
                self.assertIn(compare.clock(actual["elapsed_seconds"]), point.find("{*}title").text)
                self.assertIn(compare.clock(predicted["arrival_seconds"]), point.find("{*}title").text)
            bars = segment_plot.findall(".//{*}rect[@data-delta-seconds]")
            self.assertEqual(len(bars), len(result["segments"]))
            zero = float(segment_plot.get("data-zero-y"))
            scale = float(segment_plot.get("data-pixels-per-second"))
            target = schedule["target_seconds"]
            for segment, bar in zip(result["segments"], bars):
                predicted = next(p for p in segment["plans"] if p["target_seconds"] == target)
                delta = predicted["delta_seconds"]
                self.assertAlmostEqual(float(bar.get("data-delta-seconds")), delta)
                self.assertAlmostEqual(float(bar.get("height")), abs(delta) * scale, places=2)
                self.assertAlmostEqual(float(bar.get("y")), zero - max(0, delta) * scale, places=2)
                self.assertEqual(bar.get("fill"), time_status(delta)[1])
                self.assertIn(compare.clock(segment["actual_seconds"]), bar.find("{*}title").text)
                self.assertIn(compare.clock(predicted["seconds"]), bar.find("{*}title").text)
        self.assertTrue(all(len(values) == 1 for values in scales.values()))

    def test_time_readout_shows_actual_and_each_plan_with_cumulative_and_segment_times(self):
        import xml.etree.ElementTree as ET
        from comparison_svg import render_svg
        self.config["targets"] = ["15:00", "26:00"]
        self.config["checkpoint_overrides"] = {"wpt:1": {"rest_minutes": 5}}
        self.plan, self.route = compare.load_plan(self.path, self.config)
        result = self.build()
        root = ET.fromstring(render_svg(result))
        readout = root.find(".//{*}g[@id='checkpoint-times']")
        self.assertIsNotNone(readout)
        headers = readout.findall(".//{*}g[@class='checkpoint-header inspectable']")
        self.assertEqual(len(headers), len(result["segments"]))
        for header, cp, terrain in zip(headers, self.plan["checkpoints"][1:], result["terrain"]):
            self.assertEqual(header.get("data-cp-id"), cp["id"])
            self.assertAlmostEqual(float(header.get("data-distance-m")), cp["distance_m"])
            self.assertIn(cp["name"], "".join(header.findall("{*}text")[0].itertext()))
            self.assertIn(f'{cp["distance_m"] / 1000:.1f} km', "".join(header.itertext()))
            self.assertIn(f'{terrain["actual_distance_m"] / 1000:.3f}', header.find("{*}title").text)
        rows = readout.findall(".//{*}g[@class='time-row']")
        self.assertEqual([row.get("data-series") for row in rows], ["actual", "planned", "planned"])
        self.assertIn("累计 / 本段", "".join(readout.itertext()))
        for j, row in enumerate(rows):
            cells = row.findall("{*}g[@class='time-cell inspectable']")
            self.assertEqual(len(cells), len(result["segments"]))
            if j:
                self.assertEqual(float(row.get("data-target-seconds")), self.plan["targets_seconds"][j - 1])
            for i, cell in enumerate(cells, 1):
                if j == 0:
                    elapsed = result["checkpoints"][i]["elapsed_seconds"]
                    segment = result["segments"][i - 1]["actual_seconds"]
                else:
                    elapsed = self.plan["schedules"][j - 1]["checkpoints"][i]["arrival_seconds"]
                    segment = result["segments"][i - 1]["plans"][j - 1]["seconds"]
                self.assertEqual(cell.get("data-cp-id"), result["checkpoints"][i]["id"])
                self.assertAlmostEqual(float(cell.get("data-elapsed-seconds")), elapsed)
                self.assertAlmostEqual(float(cell.get("data-segment-seconds")), segment)
                value = cell.find("{*}text[@data-role='time-values']")
                self.assertEqual(value.text, f"{compare.clock(elapsed)} / {compare.clock(segment)}")
                self.assertEqual(cell.get("tabindex"), "0")
                self.assertIn(result["segments"][i - 1]["from_name"], cell.find("{*}title").text)

    def test_dense_checkpoint_readout_wraps_into_blocks_without_losing_values(self):
        import xml.etree.ElementTree as ET
        from comparison_svg import render_svg
        total_km = self.route.total_m / 1000
        self.config["checkpoints"] = [
            {"name": f"Station {i}", "distance_km": total_km * i / 18}
            for i in range(1, 19)
        ]
        self.plan, self.route = compare.load_plan(self.path, self.config)
        result = self.build()
        root = ET.fromstring(render_svg(result))
        blocks = root.findall(".//{*}g[@class='time-readout-block']")
        self.assertGreater(len(blocks), 1)
        actual_cells = root.findall(".//{*}g[@class='time-row'][@data-series='actual']/{*}g[@data-cp-id]")
        self.assertEqual([c.get("data-cp-id") for c in actual_cells], [cp["id"] for cp in result["checkpoints"][1:]])
        for block in blocks:
            self.assertGreaterEqual(float(block.get("data-column-width")), 200)
            rows = block.findall("{*}g[@class='time-row']")
            self.assertEqual(len(rows), len(self.plan["schedules"]) + 1)

    def test_terrain_summary_and_grouped_elevation_charts_preserve_values(self):
        import xml.etree.ElementTree as ET
        from comparison_svg import render_svg
        result = self.build()
        root = ET.fromstring(render_svg(result))
        summary = root.find(".//{*}g[@id='terrain-summary']")
        self.assertIsNotNone(summary)
        self.assertIn(f'{result["activity"]["totals"]["distance_m"] / 1000:.2f} / '
                      f'{self.plan["route"]["distance_m"] / 1000:.2f} km', "".join(summary.itertext()))
        scales = set()
        for key in ("ascent_m", "descent_m"):
            plot = root.find(f".//{{*}}g[@data-kind='{key}']")
            zero = float(plot.get("data-zero-y"))
            scale = float(plot.get("data-pixels-per-meter"))
            scales.add(scale)
            for source in ("actual", "planned"):
                bars = plot.findall(f".//{{*}}rect[@data-series='{source}']")
                self.assertEqual(len(bars), len(result["terrain"]))
                for metrics, bar in zip(result["terrain"], bars):
                    value = metrics[source + "_" + key]
                    self.assertAlmostEqual(float(bar.get("data-value-m")), value)
                    self.assertAlmostEqual(float(bar.get("height")), value * scale, places=2)
                    self.assertAlmostEqual(float(bar.get("y")), zero - value * scale, places=2)
        self.assertEqual(len(scales), 1)

    def test_close_elevation_labels_are_staggered_above_their_bars(self):
        import xml.etree.ElementTree as ET
        from comparison_svg import render_svg
        result = self.build()
        for row in result["terrain"]:
            for key in ("ascent_m", "descent_m"):
                row["actual_" + key] = 500.0
                row["planned_" + key] = 501.0
        root = ET.fromstring(render_svg(result))
        for key in ("ascent_m", "descent_m"):
            plot = root.find(f".//{{*}}g[@data-kind='{key}']")
            for group in plot.findall("{*}g[@data-actual-available]"):
                actual, planned = group.findall("{*}text")[:2]
                self.assertGreaterEqual(abs(float(actual.get("y")) - float(planned.get("y"))), 26)
                for label, bar in zip((actual, planned), group.findall("{*}rect[@data-series]")):
                    self.assertEqual(label.get("text-anchor"), "middle")
                    self.assertLess(float(label.get("y")), float(bar.get("y")))

    def test_missing_terrain_shows_unknown_and_keeps_available_plan_values(self):
        import xml.etree.ElementTree as ET
        from comparison_svg import render_svg
        result = self.build()
        for key in ("distance_m", "ascent_m", "descent_m"):
            result["terrain"][0]["actual_" + key] = None
            result["terrain"][1]["actual_" + key] = result["terrain"][1]["planned_" + key]
        root = ET.fromstring(render_svg(result))
        header = root.find(".//{*}g[@class='checkpoint-header inspectable']")
        self.assertIn("—", header.find("{*}title").text)
        for key in ("ascent_m", "descent_m"):
            unknown = root.find(f".//{{*}}g[@data-kind='{key}']/{{*}}g[@data-actual-available='false']")
            self.assertIn("—", "".join(unknown.itertext()))
            self.assertIsNone(unknown.find("{*}rect[@data-series='actual']"))
            self.assertIsNotNone(unknown.find("{*}rect[@data-series='planned']"))

    def test_svg_preserves_accessible_exact_values_and_escaped_provenance(self):
        import xml.etree.ElementTree as ET
        from comparison_svg import render_svg
        result = self.build()
        result["warnings"] = ["GPS <gap> & station override"]
        result["activity"]["activity_name"] = "Race <A> & B"
        root = ET.fromstring(render_svg(result))
        metadata = json.loads(root.find("{*}metadata").text)
        self.assertEqual(metadata["warnings"], result["warnings"])
        self.assertIn("Race <A> & B", "".join(root.itertext()))
        tips = [e.text for e in root.findall(".//{*}title") if e.text]
        self.assertTrue(any("01:06:40" in tip for tip in tips))
        self.assertTrue(root.findall(".//*[@tabindex='0']/{*}title"))
        ids = [e.get("id") for e in root.iter() if e.get("id")]
        self.assertEqual(len(ids), len(set(ids)))

    def test_time_status_uses_actual_perspective_and_rounded_ties(self):
        from comparison_svg import time_status
        self.assertEqual(time_status(60)[0], "实际领先 00:01:00")
        self.assertEqual(time_status(-60)[0], "实际落后 00:01:00")
        self.assertEqual(time_status(60, True)[0], "本段快 00:01:00")
        self.assertEqual(time_status(-60, True)[0], "本段慢 00:01:00")
        for delta in (-.49, 0, .49):
            self.assertEqual(time_status(delta)[0], "持平 00:00:00")
            self.assertEqual(time_status(delta)[1:], time_status(0)[1:])
        self.assertEqual(time_status(.5)[0], "实际领先 00:00:01")
        self.assertEqual(time_status(-.5, True)[0], "本段慢 00:00:01")
        self.assertEqual(time_status(90000)[0], "实际领先 25:00:00")

    def test_line_crossings_split_at_interpolated_zero(self):
        from comparison_svg import split_at_zero
        pieces = split_at_zero([(10, 30), (50, -10), (70, 0), (90, 20)])
        self.assertEqual(pieces, [((10, 30), (40, 0)), ((40, 0), (50, -10)),
                                  ((50, -10), (70, 0)), ((70, 0), (90, 20))])
        for start, end in pieces:
            self.assertGreaterEqual(start[1] * end[1], 0)
        self.assertEqual(split_at_zero([(0, 0), (1, 0)]), [((0, 0), (1, 0))])
        self.assertEqual(split_at_zero([(0, 0)]), [])

    def test_small_segment_differences_preserve_direction_and_seconds(self):
        from comparison_svg import minute_delta_label
        for delta in (-.49, 0, .49):
            self.assertEqual(minute_delta_label(delta), "持平")
        self.assertEqual(minute_delta_label(.5), "快1秒")
        self.assertEqual(minute_delta_label(-2.1), "慢2秒")
        self.assertEqual(minute_delta_label(5.5), "快6秒")
        self.assertEqual(minute_delta_label(60), "+1.0")
        self.assertEqual(minute_delta_label(-60), "-1.0")

    def test_metric_labels_round_after_subtraction_and_scales_cover_data(self):
        from comparison_svg import axis_limit, metric_delta_label, metric_limit
        self.assertEqual(metric_delta_label(-.5), "仓库少 1 m")
        self.assertEqual(metric_delta_label(.49), "差值 0 m")
        self.assertEqual(metric_delta_label(125.5), "仓库多 126 m")
        self.assertEqual(metric_delta_label(None), "差值 —")
        self.assertEqual(axis_limit([106 * 60, -20 * 60]), 120 * 60)
        self.assertEqual(axis_limit([-43 * 60, 26 * 60]), 50 * 60)
        for values in ([0], [None], [-.4, .9], [-125.4, 256.7], [1105.2, 0]):
            limit = metric_limit(values)
            self.assertGreater(limit, 0)
            self.assertGreaterEqual(limit, max((abs(v) for v in values if v is not None), default=0))

    def test_many_targets_keep_every_panel_and_finish_status(self):
        import xml.etree.ElementTree as ET
        from comparison_svg import render_svg, time_status
        targets = [f"01:06:{second:02d}" for second in range(36, 48)]
        self.plan, self.route = compare.load_plan(self.path, self.config, targets)
        result = self.build()
        root = ET.fromstring(render_svg(result))
        panels = root.findall(".//{*}g[@class='target-panel']")
        self.assertEqual(len(panels), len(targets))
        texts = " ".join(root.itertext())
        actual = result["activity"]["totals"]["elapsed_seconds"]
        for target, panel in zip(self.plan["targets_seconds"], panels):
            self.assertIn(time_status(target - actual)[0], texts)
            self.assertIsNotNone(panel.find("{*}g[@data-kind='segment']"))
        cells = {(p.get("data-column"), p.get("data-row")) for p in panels}
        self.assertEqual(len(cells), len(targets))


class NetworkAndCliTests(unittest.TestCase):
    def test_env_precedence_and_no_shell_evaluation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text("GARMIN_PERSONAL_API_KEY='file-key'\n")
            self.assertEqual(data.api_key(path, {"GARMIN_PERSONAL_API_KEY": "env-key"}), "env-key")
            self.assertEqual(data.api_key(path, {}), "file-key")
            path.write_text("GARMIN_PERSONAL_API_KEY=$(touch impossible)\n")
            with self.assertRaises(pace.InputError):
                data.api_key(path, {})
            with self.assertRaises(pace.InputError):
                data.api_key(None, {})

    def test_http_errors_and_timeouts_do_not_echo_secrets(self):
        for error in [
            HTTPError("https://example.test", 401, "private-key", {}, io.BytesIO(b"private-key")),
            URLError("private-key"), TimeoutError("private-key"),
        ]:
            with self.subTest(error=type(error).__name__):
                with patch("activity_data.urlopen", side_effect=error) as request:
                    with self.assertRaises(pace.InputError) as caught:
                        data.GarminClient("private-key").activities("2026-01-01", "2026-01-02")
                    self.assertNotIn("private-key", str(caught.exception))
                    self.assertEqual(request.call_count, 1)

    def test_auth_headers_and_regions(self):
        responses = []
        for payload in (b"bearer-value", b"[]"):
            response = unittest.mock.MagicMock()
            response.__enter__.return_value.read.return_value = payload
            responses.append(response)
        with patch("activity_data.urlopen", side_effect=responses) as request:
            self.assertEqual(data.GarminClient("key", region="cn").activities(
                "2026-01-01", "2026-01-02"), [])
            first, second = [c.args[0] for c in request.call_args_list]
            self.assertIn("garmin.cn", first.full_url)
            self.assertEqual(first.get_header("Authorization"), "ApiKey key")
            self.assertEqual(second.get_header("Authorization"), "Bearer bearer-value")
        with self.assertRaises(pace.InputError):
            data.GarminClient("key", region="other")

    def test_invalid_activity_id_and_dates_fail_before_network(self):
        with patch("activity_data.urlopen") as request:
            client = data.GarminClient("key")
            with self.assertRaises(pace.InputError):
                client.fetch("../12", Path("unused"))
            with self.assertRaises(pace.InputError):
                client.activities("2026-02-02", "2026-01-01")
            request.assert_not_called()

    def test_fetch_cache_permissions_and_overwrite_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            client = data.GarminClient("key")
            stream = io.BytesIO()
            with ZipFile(stream, "w") as archive:
                archive.writestr("activity.fit", b"synthetic")
            with patch.object(client, "get_json", return_value={"activityId": 123}) as details:
                with patch.object(client, "get", return_value=stream.getvalue()):
                    paths = client.fetch("123", Path(folder))
                    self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in paths))
                    self.assertEqual(json.loads(paths[0].read_text()), {"activityId": 123})
                    with self.assertRaises(pace.InputError):
                        client.fetch("123", Path(folder))
                    self.assertEqual(details.call_count, 1)

    def test_inspect_diagnostics_and_invalid_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            path = route_file(folder)
            config = Path(folder) / "config.json"
            config.write_text(json.dumps({"targets": ["01:00"]}))
            args = ["inspect", str(path), "--config", str(config), "--fit", "local.fit"]
            activity = data.activity_from_messages(messages())
            activity["records"] = [{**r, "lat": r["lat"] + .1} for r in activity["records"]]
            with patch.object(compare, "read_activity", return_value=activity):
                with patch("sys.stderr", new_callable=io.StringIO) as stderr:
                    self.assertEqual(compare.main(args), 2)
                    error_text = stderr.getvalue()
                self.assertTrue(error_text, "inspect must emit a JSON diagnostic")
                self.assertTrue(error_text.startswith("{"), repr(error_text))
                self.assertIn("offset_m", json.loads(error_text)["details"])
            with self.assertRaises(pace.InputError):
                data.activity_from_messages(messages(), {"summaryDTO": []})

    def test_generate_is_offline_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = route_file(folder)
            config = Path(folder) / "config.json"
            config.write_text(json.dumps({"targets": ["01:00"]}))
            output = Path(folder) / "out"
            args = ["generate", str(path), "--config", str(config), "--fit", "local.fit",
                    "--targets", "01:00", "--output-dir", str(output)]
            with patch.object(compare, "read_activity", return_value=data.activity_from_messages(messages())):
                with patch("activity_data.urlopen", side_effect=AssertionError("Must be offline")):
                    with patch("sys.stdout", new_callable=io.StringIO):
                        self.assertEqual(compare.main(args), 0)
                    self.assertEqual([p.name for p in output.iterdir()], ["garmin-comparison.svg"])
                    with patch("sys.stderr", new_callable=io.StringIO):
                        self.assertEqual(compare.main(args), 2)
                    with patch("sys.stdout", new_callable=io.StringIO):
                        self.assertEqual(compare.main(args + ["--overwrite", "--export-json"]), 0)
                    self.assertTrue((output / "garmin-comparison.json").is_file())


if __name__ == "__main__":
    unittest.main()
