#!/usr/bin/env python3
"""Prepare the MGW50K example and rebuild its comparisons offline."""

import argparse
from bisect import bisect_left
import hashlib
from html import escape
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "skills/even-effort-pace-chart/scripts"))
import pace_chart as pace


SOURCE_NAME = "2026京东大境门古长城越野赛by UTMB®MGW50K.gpx"
FILLED_NAME = "MGW50K-elevation-filled.gpx"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_minutes(value):
    hours, minutes = map(int, value.split(":"))
    if hours < 0 or not 0 <= minutes < 60:
        raise ValueError(f"Invalid elapsed time: {value}")
    return hours * 60 + minutes


def chart_minutes(seconds):
    return math.floor(seconds / 60 + 1e-9)


def fill_elevations(root):
    points = root.findall(".//{*}trkpt")
    if not points:
        raise ValueError("No track points")
    coords = [(float(p.attrib["lat"]), float(p.attrib["lon"])) for p in points]
    distances = [0.0]
    for a, b in zip(coords, coords[1:]):
        distances.append(distances[-1] + pace.haversine(a, b))
    elevations = [p.findtext("{*}ele") for p in points]
    known = [i for i, z in enumerate(elevations) if z and math.isfinite(float(z))]
    if not known or known[0] != 0 or known[-1] != len(points) - 1:
        raise ValueError("Missing endpoint elevation; extrapolation is not supported")
    gaps = []
    for left, right in zip(known, known[1:]):
        if right == left + 1:
            continue
        span = distances[right] - distances[left]
        if span <= 0:
            raise ValueError("Missing elevations have no horizontal interpolation span")
        start, end = float(elevations[left]), float(elevations[right])
        for i in range(left + 1, right):
            value = start + (end - start) * (distances[i] - distances[left]) / span
            element = points[i].find("{*}ele")
            if element is None:
                prefix = points[i].tag.rsplit("}", 1)[0] + "}" if "}" in points[i].tag else ""
                element = ET.Element(prefix + "ele")
                points[i].insert(0, element)
            element.text = f"{value:.12f}"
        gaps.append({
            "first_point_index": left + 1, "last_point_index": right - 1,
            "missing_points": right - left - 1,
            "start_distance_m": distances[left], "end_distance_m": distances[right],
            "span_m": span, "start_elevation_m": start, "end_elevation_m": end,
        })
    return {
        "method": "Linear elevation interpolation along horizontal distance between known endpoints",
        "point_index_basis": "zero-based",
        "source_points": len(points),
        "missing_points": sum(g["missing_points"] for g in gaps),
        "gaps": gaps,
    }


def lap_estimate(laps, distance_m, key):
    if not laps or any(lap.get(key) is None for lap in laps):
        return None
    if distance_m < 0 or distance_m > laps[-1]["distance_m"] + 1e-6:
        return None
    previous_distance, previous_value = 0.0, 0.0
    for lap in laps:
        distance, value = lap["distance_m"], lap[key]
        if distance <= previous_distance:
            raise ValueError("Lap distances must increase")
        if distance_m <= distance:
            return previous_value + (value - previous_value) * (
                distance_m - previous_distance
            ) / (distance - previous_distance)
        previous_distance, previous_value = distance, value
    return None


def match_checkpoints(records, candidates):
    if len(records) < 2:
        raise ValueError("Need at least two recorded positions")
    for a, b in zip(records, records[1:]):
        if b["distance_m"] < a["distance_m"] or b["elapsed_seconds"] < a["elapsed_seconds"]:
            raise ValueError("Recorded distance/time must be monotonic")
    coords = [(r["lat"], r["lon"], 0.0) for r in records]
    samples = [pace.Sample(0, 0)]
    for a, b in zip(coords, coords[1:]):
        samples.append(pace.Sample(samples[-1].distance_m + pace.haversine(a, b), 0))
    route = pace.Route(coords, samples, [])
    distances = [s.distance_m for s in samples]
    result, previous = [], -1
    for candidate in candidates:
        options = pace.projection_options(route, candidate)
        if len(options) != 1 or options[0]["offset_m"] > 100:
            raise ValueError(f"Ambiguous/off-route station: {candidate['name']}")
        position = options[0]["distance_m"]
        if position <= previous:
            raise ValueError("Recorded checkpoint order is reversed")
        right = max(1, bisect_left(distances, position))
        left = right - 1
        width = distances[right] - distances[left]
        fraction = (position - distances[left]) / width if width else 0
        entry = {"name": candidate["name"], "offset_m": options[0]["offset_m"]}
        for key in ("distance_m", "elapsed_seconds"):
            entry[key] = records[left][key] + fraction * (records[right][key] - records[left][key])
        result.append(entry)
        previous = position
    return result


def prepare_route(source):
    target = HERE / SOURCE_NAME
    if source.resolve() != target.resolve():
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise ValueError("Existing source GPX differs")
        target.write_bytes(source.read_bytes())
    tree = ET.parse(target)
    report = fill_elevations(tree.getroot())
    if "}" in tree.getroot().tag:
        ET.register_namespace("", tree.getroot().tag[1:].split("}")[0])
    tree.write(HERE / FILLED_NAME, encoding="utf-8", xml_declaration=True)
    report.update({
        "source_file": SOURCE_NAME, "source_sha256": sha256(target),
        "filled_file": FILLED_NAME, "filled_sha256": sha256(HERE / FILLED_NAME),
    })
    write_json(HERE / "elevation-repair.json", report)
    print(f"Filled {report['missing_points']} elevations; source GPX preserved")


def prepare_activity(fit_path, detail_path):
    from zipfile import ZipFile
    from garmin_fit_sdk import Decoder, Stream

    with ZipFile(fit_path) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".fit")]
        if len(names) != 1:
            raise ValueError("Expected exactly one FIT file")
        binary = archive.read(names[0])
    messages, errors = Decoder(Stream.from_byte_array(bytearray(binary))).read()
    if errors:
        raise ValueError(f"FIT decode failed: {errors}")
    sessions = messages.get("session_mesgs", [])
    if len(sessions) != 1:
        raise ValueError("Expected a single-session activity")
    session = sessions[0]
    details = read_json(detail_path)
    summary = details["summaryDTO"]
    records = []
    for record in messages["record_mesgs"]:
        required = ("position_lat", "position_long", "distance", "timestamp")
        if not all(record.get(key) is not None for key in required):
            continue
        records.append({
            "lat": record["position_lat"] * 180 / 2 ** 31,
            "lon": record["position_long"] * 180 / 2 ** 31,
            "distance_m": record["distance"],
            "elapsed_seconds": (record["timestamp"] - session["start_time"]).total_seconds(),
        })
    route = pace.load_route(HERE / FILLED_NAME)
    matches = match_checkpoints(records, route.candidates[1:])
    laps, cumulative_distance, ascent, descent = [], 0.0, 0.0, 0.0
    for lap in sorted(messages.get("lap_mesgs", []), key=lambda item: item["start_time"]):
        length = lap.get("total_distance")
        if length is None or length <= 0:
            raise ValueError("A FIT lap has missing or nonpositive distance")
        cumulative_distance += length
        ascent = ascent + lap["total_ascent"] if ascent is not None and lap.get("total_ascent") is not None else None
        descent = descent + lap["total_descent"] if descent is not None and lap.get("total_descent") is not None else None
        laps.append({"distance_m": cumulative_distance, "ascent_m": ascent, "descent_m": descent})
    for match in matches:
        match["ascent_m"] = lap_estimate(laps, match["distance_m"], "ascent_m")
        match["descent_m"] = lap_estimate(laps, match["distance_m"], "descent_m")
    totals = {
        "distance_m": summary["distance"], "elapsed_seconds": summary["elapsedDuration"],
        "timer_seconds": summary["duration"], "moving_seconds": summary["movingDuration"],
        "ascent_m": summary["elevationGain"], "descent_m": summary["elevationLoss"],
    }
    if abs(totals["distance_m"] - records[-1]["distance_m"]) > 1:
        raise ValueError("Recorded and platform finish distances differ")
    start = {"name": "起点", "distance_m": 0, "elapsed_seconds": 0, "ascent_m": 0, "descent_m": 0, "offset_m": 0}
    finish = {"name": "终点", **{k: totals[k] for k in ("distance_m", "elapsed_seconds", "ascent_m", "descent_m")}}
    output = {
        "activity_id": details["activityId"], "activity_name": details["activityName"],
        "start_time_local": summary["startTimeLocal"],
        "source": "Previously downloaded Garmin Connect activity summary and original FIT",
        "fit_sdk_version": "21.218.0",
        "source_fit_zip_sha256": sha256(fit_path), "source_details_sha256": sha256(detail_path),
        "time_basis": "Elapsed time including stops; projected station passage, not official timing",
        "station_elevation_basis": "Estimated by recorded distance within FIT laps; finish uses platform totals",
        "record_count": len(records), "lap_count": len(laps),
        "lap_totals": laps[-1] if laps else None, "totals": totals,
        "checkpoints": [start, *matches, finish],
    }
    write_json(HERE / "garmin-activity.json", output)
    print(f"Prepared activity {output['activity_id']}: {len(matches)} matched stations")


def build_data():
    plan = pace.build_plan(HERE / FILLED_NAME, read_json(HERE / "config.json"))
    reference = read_json(HERE / "runart-reference.json")
    activity = read_json(HERE / "garmin-activity.json")
    targets = reference["targets_hours"]
    if plan["targets_seconds"] != [h * 3600 for h in targets]:
        raise ValueError("Reference and local target columns differ")
    stations = reference["checkpoints"]
    if len(stations) != len(plan["checkpoints"]) or len(stations) != len(activity["checkpoints"]):
        raise ValueError("Checkpoint counts differ")
    local, ascent, descent, reference_ascent, reference_descent = [], 0, 0, 0, 0
    for index, (source, cp, actual) in enumerate(zip(stations, plan["checkpoints"], activity["checkpoints"])):
        if len(source["elapsed"]) != len(targets):
            raise ValueError("Missing reference time values")
        for value in source["elapsed"]:
            parse_minutes(value)
        if 0 < index < len(stations) - 1:
            station_id = source["label"].split()[0]
            if not all(item["name"].startswith(station_id) for item in (cp, actual)):
                raise ValueError("Checkpoint identities differ")
        ascent += cp["ascent_m"]
        descent += cp["descent_m"]
        reference_ascent += source["ascent_m"]
        reference_descent += source["descent_m"]
        source["cumulative_ascent_m"] = reference_ascent
        source["cumulative_descent_m"] = reference_descent
        times = [chart_minutes(s["checkpoints"][index]["arrival_seconds"]) for s in plan["schedules"]]
        local.append({
            "label": source["label"], "distance_km": cp["distance_m"] / 1000,
            "ascent_m": cp["ascent_m"], "descent_m": cp["descent_m"],
            "cumulative_ascent_m": ascent, "cumulative_descent_m": descent,
            "elapsed_minutes": times,
            "delta_minutes": [t - parse_minutes(s) for t, s in zip(times, source["elapsed"])],
        })
    for col in range(len(targets)):
        elapsed = [parse_minutes(cp["elapsed"][col]) for cp in stations]
        if elapsed != sorted(elapsed) or elapsed[0] != 0:
            raise ValueError("Reference elapsed times must start at zero and increase")
    return {
        "source_hashes": {name: sha256(HERE / name) for name in (
            FILLED_NAME, "config.json", "runart-reference.json", "garmin-activity.json",
        )},
        "targets_hours": targets, "parameters": plan["parameters"],
        "reference": reference, "local": {"checkpoints": local}, "garmin": activity,
    }


INK, MUTED, TEAL, RUST, BLUE = "#203c46", "#627780", "#126b70", "#aa472e", "#406da4"


def clock(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def signed(value, places=0):
    return f"{0:.{places}f}" if abs(value) < 0.5 * 10 ** -places else f"{value:+.{places}f}"


def delta_color(delta):
    return TEAL if delta < 0 else RUST if delta > 0 else MUTED


def shade(delta):
    end = (147, 207, 204) if delta < 0 else (237, 171, 139)
    amount = min(abs(delta) / 15, 1)
    return "#" + "".join(f"{round(a + (b - a) * amount):02x}" for a, b in zip((246, 248, 246), end))


class SVG:
    def __init__(self, width, height, title):
        self.width, self.height = width, height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">',
            f'<title id="title">{escape(title)}</title>',
            '<style>text{font-family:"PingFang SC","Noto Sans CJK SC","Microsoft YaHei",sans-serif;'
            'font-variant-numeric:tabular-nums}</style>',
        ]
        self.rect(0, 0, width, height, "#f5f4ef")
        self.rect(0, 0, width, 10, TEAL)

    def rect(self, x, y, width, height, fill="#ffffff", radius=0):
        self.parts.append(f'<rect x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" rx="{radius}" fill="{fill}"/>')

    def text(self, x, y, value, size=22, fill=INK, weight=400, anchor="start"):
        self.parts.append(
            f'<text x="{x:g}" y="{y:g}" font-size="{size}" fill="{fill}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{escape(str(value))}</text>'
        )

    def path(self, points, color, dashed=False):
        coords = " ".join(f"{'M' if i == 0 else 'L'}{x:g} {y:g}" for i, (x, y) in enumerate(points))
        dash = ' stroke-dasharray="9 6"' if dashed else ""
        self.parts.append(f'<path d="{coords}" fill="none" stroke="{color}" stroke-width="3"{dash}/>')

    def save(self, name, data):
        self.parts.insert(2, f'<metadata>{escape(json.dumps(data["source_hashes"]))}</metadata>')
        (HERE / name).write_text("\n".join([*self.parts, "</svg>"]) + "\n", encoding="utf-8")


def reference_chart(data):
    svg = SVG(2720, 1370, "大境门 MGW50K：耐力学社与仓库方案对比")
    svg.text(64, 78, "大境门 MGW50K", 45, weight=700)
    svg.text(2656, 76, "耐力学社 × 仓库方案", 30, anchor="end")
    svg.text(64, 125, "5–12.5 小时 · 每隔 30 分钟 · 16 组方案", 24, MUTED)
    source = data["reference"]["checkpoints"]
    local = data["local"]["checkpoints"]
    for index, (title, key, unit) in enumerate((
        ("全程距离", "distance_km", "km"),
        ("累计爬升", "cumulative_ascent_m", "m"),
        ("累计下降", "cumulative_descent_m", "m"),
    )):
        x = 64 + index * 872
        svg.rect(x, 157, 848, 126, radius=13)
        svg.text(x + 24, 191, title, 21, MUTED)
        a, b = source[-1][key], local[-1][key]
        pair = f"{a:.1f} → {b:.2f}" if index == 0 else f"{a:.0f} → {b:.0f}"
        svg.text(x + 24, 242, f"{pair} {unit}", 36, weight=650)
        svg.text(x + 24, 269, "耐力学社 → 仓库", 18, MUTED)
        svg.text(x + 824, 269, f"{signed(b - a, 2 if index == 0 else 0)} {unit}", 23, RUST, anchor="end")
    svg.text(64, 331, "01  各站累计经过时间", 28, weight=700)
    svg.text(64, 371, "上行：耐力学社 → 仓库（HH:MM）；下行：仓库 − 耐力学社（分钟）", 22, MUTED)
    svg.text(2656, 371, "绿色：仓库更早    橙色：仓库更晚", 22, MUTED, anchor="end")
    left, width, top = 300, 2356 / 16, 430
    svg.text(78, 412, "站点", 22, MUTED, 600)
    for col, target in enumerate(data["targets_hours"]):
        svg.text(left + (col + 0.5) * width, 412, f"{target:g} h", 23, weight=650, anchor="middle")
    for row, (a, b) in enumerate(zip(source[1:], local[1:])):
        y = top + row * 72
        svg.rect(64, y, left - 64, 70, radius=4)
        svg.text(78, y + 39, a["label"], 23, weight=600)
        for col in range(16):
            x = left + col * width
            delta = b["delta_minutes"][col]
            svg.rect(x + 1, y, width - 2, 70, shade(delta), 4)
            svg.text(x + width / 2, y + 27, f'{a["elapsed"][col]} → {clock(b["elapsed_minutes"][col])}',
                     18, anchor="middle")
            svg.text(x + width / 2, y + 58, signed(delta), 25, delta_color(delta), 650, "middle")
    svg.text(64, 920, "02  地形数据", 28, weight=700)
    svg.text(2656, 920, "每组依次为：耐力学社 / 仓库 / 差值", 22, MUTED, anchor="end")
    group_width = (2656 - left) / 3
    for group, title in enumerate(("累计距离 / km", "本段爬升 / m", "本段下降 / m")):
        x = left + group * group_width
        svg.text(x + group_width / 2, 962, title, 24, weight=600, anchor="middle")
        for col, label in enumerate(("耐力学社", "仓库", "差值")):
            svg.text(x + (col + 0.5) * group_width / 3, 990, label, 20, MUTED, anchor="middle")
    svg.text(78, 990, "站点", 21, MUTED)
    for row, (a, b) in enumerate(zip(source[1:], local[1:])):
        y = 1009 + row * 38
        svg.rect(64, y, 2592, 38, "#ffffff" if row % 2 == 0 else "#eaf0ed")
        svg.text(78, y + 27, a["label"], 22)
        for group, key in enumerate(("distance_km", "ascent_m", "descent_m")):
            values = [f'{a[key]:.1f}' if group == 0 else f'{a[key]:.0f}',
                      f'{b[key]:.2f}' if group == 0 else f'{b[key]:.0f}',
                      signed(b[key] - a[key], 2 if group == 0 else 0)]
            for col, value in enumerate(values):
                x = left + group * group_width + (col + 0.5) * group_width / 3
                svg.text(x, y + 27, value, 22, delta_color(b[key] - a[key]) if col == 2 else INK,
                         600 if col == 2 else 400, "middle")
    svg.text(64, 1294, "来源：用户提供的耐力学社 / RunArt.Net 截图及本仓库 50K 配速表。时间差按两表显示的整分钟相减；起点均为 00:00，省略。", 20, MUTED)
    svg.text(64, 1331, "原图终点时间照录，未归一化；地形列按数值含义转录（原图表头疑似错位）。括号内配速不参与对比。", 20, MUTED)
    svg.save("runart-comparison.svg", data)


def time_plot(svg, x, y, width, height, target, data):
    source, local, actual = data["reference"]["checkpoints"], data["local"]["checkpoints"], data["garmin"]["checkpoints"]
    col = data["targets_hours"].index(target)
    svg.text(x, y - 35, f"{target:g} 小时方案", 26, weight=650)
    graph_x, graph_y, graph_w, graph_h = x + 58, y, width - 85, height
    for hour in range(8):
        py = graph_y + graph_h - hour / 7 * graph_h
        svg.path([(graph_x, py), (graph_x + graph_w, py)], "#dde5e6")
        svg.text(graph_x - 14, py + 7, f"{hour}h", 18, MUTED, anchor="end")
    for i, cp in enumerate(source):
        svg.text(graph_x + i * graph_w / 6, graph_y + graph_h + 29,
                 "起点" if i == 0 else "终点" if i == 6 else cp["label"].split()[0], 19, MUTED, anchor="middle")
    series = [
        ([parse_minutes(cp["elapsed"][col]) / 60 for cp in source], BLUE, True),
        ([cp["elapsed_minutes"][col] / 60 for cp in local], TEAL, False),
        ([cp["elapsed_seconds"] / 3600 for cp in actual], RUST, False),
    ]
    for values, color, dashed in series:
        points = [(graph_x + i * graph_w / 6, graph_y + graph_h - value / 7 * graph_h)
                  for i, value in enumerate(values)]
        svg.path(points, color, dashed)
        for px, py in points:
            svg.rect(px - 4, py - 4, 8, 8, color, 4)


def activity_chart(data):
    svg = SVG(2200, 1650, "大境门 MGW50K：佳明实际活动与两份配速表对比")
    svg.text(64, 77, "大境门 MGW50K · 实际活动对照", 42, weight=700)
    actual = data["garmin"]
    total = actual["totals"]
    seconds = round(total["elapsed_seconds"])
    elapsed = f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"
    svg.text(64, 122, f'佳明：2026-09-12「{actual["activity_name"]}」 · 累计经过 {elapsed}（含停留）', 24, MUTED)
    source, local, records = data["reference"]["checkpoints"], data["local"]["checkpoints"], actual["checkpoints"]
    for i, (title, key, total_key, unit) in enumerate((
        ("全程距离", "distance_km", "distance_m", "km"),
        ("累计爬升", "cumulative_ascent_m", "ascent_m", "m"),
        ("累计下降", "cumulative_descent_m", "descent_m", "m"),
    )):
        x = 64 + i * 698
        svg.rect(x, 158, 674, 126, radius=13)
        own = total[total_key] / 1000 if i == 0 else total[total_key]
        svg.text(x + 24, 192, title, 21, MUTED)
        svg.text(x + 24, 242, f"{own:.2f} {unit}" if i == 0 else f"{own:.0f} {unit}", 37, RUST, 650)
        svg.text(x + 650, 193, "佳明平台", 20, RUST, anchor="end")
        a, b = source[-1][key], local[-1][key]
        other = f"{a:.1f} / {b:.2f}" if i == 0 else f"{a:.0f} / {b:.0f}"
        svg.text(x + 24, 269, f"耐力学社 / 仓库：{other} {unit}", 21, MUTED)
    svg.text(64, 332, "01  各站累计经过时间", 28, weight=700)
    for x, color, label in ((1270, BLUE, "耐力学社"), (1550, TEAL, "仓库方案"), (1830, RUST, "佳明实际")):
        svg.path([(x, 324), (x + 45, 324)], color, color == BLUE)
        svg.text(x + 58, 332, label, 22, color)
    time_plot(svg, 64, 403, 1016, 272, 6, data)
    time_plot(svg, 1120, 403, 1016, 272, 6.5, data)
    positions = [75, 470, 800, 1110, 1515, 1920]
    labels = ["站点", "耐力学社 6h", "仓库 6h", "佳明实际", "耐力学社 6.5h", "仓库 6.5h"]
    for i, (x, label) in enumerate(zip(positions, labels)):
        svg.text(x, 752, label, 22, MUTED, 600, "start" if i == 0 else "middle")
    for row in range(1, 7):
        y = 773 + (row - 1) * 43
        svg.rect(64, y, 2072, 43, "#ffffff" if row % 2 else "#eaf0ed")
        a, b, c = source[row], local[row], records[row]
        values = [a["label"], a["elapsed"][2], clock(b["elapsed_minutes"][2]),
                  clock(chart_minutes(c["elapsed_seconds"])), a["elapsed"][3], clock(b["elapsed_minutes"][3])]
        for i, (x, value) in enumerate(zip(positions, values)):
            svg.text(x, y + 30, value, 24, RUST if i == 3 else INK,
                     600 if i == 3 else 400, "start" if i == 0 else "middle")
    svg.text(64, 1100, "02  各站累计距离与累计爬升、下降", 28, weight=700)
    svg.text(2136, 1100, "佳明分站爬升、下降为逐圈插值估算", 21, MUTED, anchor="end")
    left, group_width = 280, (2136 - 280) / 3
    for group, title in enumerate(("累计距离 / km", "累计爬升 / m", "累计下降 / m")):
        x = left + group * group_width
        svg.text(x + group_width / 2, 1147, title, 24, weight=600, anchor="middle")
        for col, label in enumerate(("耐力学社", "仓库", "佳明")):
            svg.text(x + (col + 0.5) * group_width / 3, 1177, label, 21,
                     RUST if col == 2 else MUTED, anchor="middle")
    svg.text(75, 1177, "站点", 21, MUTED)
    for row in range(1, 7):
        y = 1197 + (row - 1) * 44
        svg.rect(64, y, 2072, 44, "#ffffff" if row % 2 else "#eaf0ed")
        a, b, c = source[row], local[row], records[row]
        svg.text(75, y + 31, a["label"], 23)
        for group, (key, actual_key) in enumerate((
            ("distance_km", "distance_m"), ("cumulative_ascent_m", "ascent_m"), ("cumulative_descent_m", "descent_m"),
        )):
            value = c[actual_key]
            values = [a[key], b[key], value / 1000 if group == 0 else value]
            for col, val in enumerate(values):
                label = "—" if val is None else f"{val:.2f}" if group == 0 else f"{val:.0f}"
                svg.text(left + group * group_width + (col + 0.5) * group_width / 3, y + 31,
                         label, 23, RUST if col == 2 else INK, 600 if col == 2 else 400, "middle")
    svg.text(64, 1530, "时间为轨迹经过时间，非官方打卡；表内按整分钟显示。分站距离使用 FIT 记录累计距离，终点使用佳明平台汇总。", 20, MUTED)
    svg.text(64, 1567, "佳明分站爬升、下降按逐圈距离线性插值；逐圈爬升合计 2204 m，平台全程为 2205 m，未按比例调整。", 20, MUTED)
    svg.text(64, 1604, "来源：耐力学社 / RunArt.Net 截图、本仓库配速表、佳明活动缓存。6h、6.5h 两档均保留原始目标时间。", 20, MUTED)
    svg.save("garmin-comparison.svg", data)


def generate():
    data = build_data()
    write_json(HERE / "comparison-data.json", data)
    reference_chart(data)
    activity_chart(data)
    print("Generated comparison-data.json, runart-comparison.svg, garmin-comparison.svg")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    route = sub.add_parser("prepare-route")
    route.add_argument("source", type=Path)
    activity = sub.add_parser("prepare-activity")
    activity.add_argument("--fit", type=Path, required=True)
    activity.add_argument("--details", type=Path, required=True)
    sub.add_parser("generate")
    args = parser.parse_args()
    if args.command == "prepare-route":
        prepare_route(args.source)
    elif args.command == "prepare-activity":
        prepare_activity(args.fit, args.details)
    else:
        generate()


if __name__ == "__main__":
    main()
