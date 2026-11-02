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

    def test_renderer_retains_seconds_and_unknown_metrics(self):
        import xml.etree.ElementTree as ET
        from comparison_svg import render_svg
        self.activity["laps"] = []
        result = self.build()
        svg = render_svg(result)
        root = ET.fromstring(svg)
        ids = {item.get("id") for item in root.iter()}
        self.assertTrue({"cumulative-times", "terrain", "segment-times", "time-curves"} <= ids)
        self.assertIn("01:06:40", "".join(root.itertext()))
        self.assertIn("—", svg)
        self.assertEqual(len(root.findall(".//{*}path[@data-series='garmin']")), 2)


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
