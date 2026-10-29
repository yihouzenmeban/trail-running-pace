#!/usr/bin/env python3
"""Rebuild the SVG comparison using the screenshot transcription and local chart."""

import hashlib
import json
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WIDTH, HEIGHT = 2560, 1880
INK, MUTED, LINE = "#203c46", "#627780", "#dde5e6"
TEAL, RUST = "#126b70", "#a9442e"


def minutes(value):
    hours, mins = map(int, value.split(":"))
    if hours < 0 or not 0 <= mins < 60:
        raise ValueError(f"Invalid elapsed time: {value}")
    return hours * 60 + mins


def clock(value):
    return f"{value // 60:02d}:{value % 60:02d}"


def signed(value, places=0):
    if abs(value) < 0.5 * 10 ** -places:
        return f"{0:.{places}f}"
    return f"{value:+.{places}f}"


def color(delta):
    return TEAL if delta < 0 else RUST if delta > 0 else MUTED


def shade(delta):
    neutral = (246, 248, 246)
    endpoint = (147, 207, 204) if delta < 0 else (237, 171, 139)
    weight = min(abs(delta) / 15, 1)
    return "#" + "".join(
        f"{round(a + (b - a) * weight):02x}"
        for a, b in zip(neutral, endpoint)
    )


def main():
    reference_path = ROOT / "runart-reference.json"
    chart_path = ROOT / "pace-chart.json"
    reference = json.loads(reference_path.read_text())
    chart = json.loads(chart_path.read_text())
    checkpoints = reference["checkpoints"]
    local = chart["checkpoints"]
    targets = reference["targets_hours"]
    schedules = chart["schedules"]
    if len(local) != len(checkpoints) or len(targets) != len(schedules):
        raise ValueError("The two charts must have matching checkpoint/target counts")
    if [s["target_seconds"] for s in schedules] != [h * 3600 for h in targets]:
        raise ValueError("The target columns do not match")
    if len({c["label"] for c in checkpoints}) != len(checkpoints):
        raise ValueError("Duplicate reference checkpoints")
    for index, cp in enumerate(checkpoints):
        if len(cp["elapsed"]) != len(targets):
            raise ValueError(f"Missing target values for {cp['label']}")
        if index not in (0, len(checkpoints) - 1):
            station_id = cp["label"].split()[0]
            if not local[index]["name"].startswith(station_id):
                raise ValueError(f"Checkpoint order differs at {cp['label']}")
    for col, schedule in enumerate(schedules):
        if len(schedule["checkpoints"]) != len(checkpoints):
            raise ValueError("Missing local checkpoint times")
        official = [minutes(cp["elapsed"][col]) for cp in checkpoints]
        own = [int(cp["arrival_seconds"] // 60) for cp in schedule["checkpoints"]]
        if official[0] != 0 or own[0] != 0:
            raise ValueError("Both elapsed timelines must start at zero")
        if official != sorted(official) or own != sorted(own):
            raise ValueError("Checkpoint times must be monotonic")
        if own[-1] != targets[col] * 60:
            raise ValueError("Local finish time differs from its target")
    for key in ("ascent_m", "descent_m"):
        if abs(sum(c[key] for c in local) - chart["route"][key]) > 0.01:
            raise ValueError(f"Local segment totals do not match: {key}")

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">',
        "<title id=\"title\">大境门 DGW100K：耐力学社与仓库方案对比</title>",
        "<desc id=\"desc\">10至24小时共15组方案的各站累计经过时间、"
        "分钟差，以及距离和分段爬升下降对比。</desc>",
    ]
    provenance = {
        "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        "chart_sha256": hashlib.sha256(chart_path.read_bytes()).hexdigest(),
        "time_delta": "floor(local arrival seconds / 60) - reference displayed minutes",
    }
    svg.append(f"<metadata>{escape(json.dumps(provenance))}</metadata>")
    svg.append(
        '<style>text{font-family:"PingFang SC","Noto Sans CJK SC",'
        '"Microsoft YaHei",sans-serif;font-variant-numeric:tabular-nums}</style>'
    )

    def rect(x, y, w, h, fill, radius=0):
        svg.append(
            f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" '
            f'rx="{radius}" fill="{fill}"/>'
        )

    def text(x, y, value, size=22, fill=INK, weight=400, anchor="start"):
        svg.append(
            f'<text x="{x:g}" y="{y:g}" font-size="{size}" fill="{fill}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{escape(str(value))}</text>'
        )

    def line(x1, y1, x2, y2):
        svg.append(
            f'<path d="M{x1:g} {y1:g}H{x2:g}" stroke="{LINE}"/>'
            if y1 == y2 else
            f'<path d="M{x1:g} {y1:g}L{x2:g} {y2:g}" stroke="{LINE}"/>'
        )

    rect(0, 0, WIDTH, HEIGHT, "#f5f4ef")
    rect(0, 0, WIDTH, 12, TEAL)
    text(64, 79, "大境门 DGW100K", 46, weight=700)
    text(2496, 76, "耐力学社 × 仓库方案", 31, anchor="end")
    text(64, 127, "10–24 小时 · 每小时一组 · 各站累计经过时间与地形数据对照", 24, MUTED)

    source_totals = [
        checkpoints[-1]["distance_km"],
        sum(c["ascent_m"] for c in checkpoints),
        sum(c["descent_m"] for c in checkpoints),
    ]
    own_totals = [
        chart["route"]["distance_m"] / 1000,
        chart["route"]["ascent_m"],
        chart["route"]["descent_m"],
    ]
    for i, (label, unit, source, own) in enumerate(zip(
        ("全程距离", "累计爬升", "累计下降"),
        ("km", "m", "m"), source_totals, own_totals,
    )):
        x = 64 + i * 818
        rect(x, 163, 796, 133, "#ffffff", 14)
        text(x + 24, 196, label, 22, MUTED)
        pair = f"{source:.1f} → {own:.2f}" if i == 0 else f"{source:.0f} → {own:.0f}"
        text(x + 24, 249, pair, 37, weight=650)
        text(x + 24, 278, "耐力学社 → 仓库", 18, MUTED)
        text(x + 770, 247, unit, 22, MUTED, anchor="end")
        delta = own - source
        text(x + 770, 278, f"{signed(delta, 2 if i == 0 else 0)} {unit} / {delta / source:+.1%}",
             21, RUST, anchor="end")

    text(64, 352, "01  到站时间对比", 29, weight=700)
    text(64, 391, "每格上行：耐力学社 → 仓库（HH:MM）；下行：仓库 − 耐力学社（分钟）", 22, MUTED)
    rect(1940, 371, 25, 25, shade(-12), 4)
    text(1978, 391, "负数：仓库更早", 21, TEAL)
    rect(2220, 371, 25, 25, shade(12), 4)
    text(2258, 391, "正数：仓库更晚", 21, RUST)
    grid_x, cell_w, row_h, top = 284, 2212 / 15, 64, 452
    text(78, 434, "站点", 22, MUTED, 600)
    for col, target in enumerate(targets):
        x = grid_x + col * cell_w
        text(x + cell_w / 2, 434, f"{target} h", 23, INK, 650, "middle")
    for row, cp in enumerate(checkpoints[1:], 1):
        y = top + (row - 1) * row_h
        rect(64, y, 220, row_h - 2, "#ffffff", 4)
        text(78, y + 36, cp["label"], 21, weight=600)
        for col, schedule in enumerate(schedules):
            own_minutes = int(schedule["checkpoints"][row]["arrival_seconds"] // 60)
            source_minutes = minutes(cp["elapsed"][col])
            delta = own_minutes - source_minutes
            x = grid_x + col * cell_w
            rect(x + 1, y, cell_w - 2, row_h - 2, shade(delta), 4)
            text(x + cell_w / 2, y + 23,
                 f"{cp['elapsed'][col]} → {clock(own_minutes)}", 18, INK, 400, "middle")
            text(x + cell_w / 2, y + 51, signed(delta), 24, color(delta), 650, "middle")

    text(64, 1216, "02  地形数据对比", 29, weight=700)
    text(2496, 1216, "单元格顺序：耐力学社 / 仓库 / 差值", 22, MUTED, anchor="end")
    groups = [(300, 732, "累计距离 / km"), (1032, 732, "本段爬升 / m"), (1764, 732, "本段下降 / m")]
    text(78, 1287, "站点", 22, MUTED, 600)
    for x, width, title in groups:
        text(x + width / 2, 1258, title, 24, weight=600, anchor="middle")
        for col, label in enumerate(("耐力学社", "仓库", "差值")):
            text(x + (col + 0.5) * width / 3, 1287, label, 20, MUTED, anchor="middle")
    terrain_rows = []
    for index, cp in enumerate(checkpoints[1:], 1):
        terrain_rows.append((
            cp["label"],
            [cp["distance_km"], cp["ascent_m"], cp["descent_m"]],
            [local[index]["distance_m"] / 1000, local[index]["ascent_m"], local[index]["descent_m"]],
        ))
    terrain_rows.append(("全程", source_totals, own_totals))
    for row, (label, source_values, own_values) in enumerate(terrain_rows):
        y = 1303 + row * 35
        total = row == len(terrain_rows) - 1
        rect(64, y, 2432, 35, "#e4eeec" if total else "#ffffff" if row % 2 == 0 else "#f0f2ef")
        text(78, y + 25, label, 21, weight=650 if total else 400)
        for i, ((x, width, _), source, own) in enumerate(zip(groups, source_values, own_values)):
            values = (
                f"{source:.1f}" if i == 0 else f"{source:.0f}",
                f"{own:.2f}" if i == 0 else f"{own:.0f}",
                signed(own - source, 2 if i == 0 else 0),
            )
            for col, value in enumerate(values):
                text(x + (col + 0.5) * width / 3, y + 25, value, 21,
                     color(own - source) if col == 2 else INK,
                     650 if total or col == 2 else 400, "middle")
    line(64, 1748, 2496, 1748)
    text(64, 1782, "来源：用户提供的耐力学社 / RunArt.Net 截图；仓库 examples/大境门/pace-chart.json。起点均为 00:00，省略。", 20, MUTED)
    text(64, 1816, "时间按两表显示的整分钟比较；原图终点保留 09:57–23:58 等原值，未归一化。括号内配速未参与对比。", 20, MUTED)
    text(64, 1850, "地形列按数值含义转录：原图 SEG / GAIN / LOSS 表头疑似错位；全程爬升、下降由原图分段值求和。", 20, MUTED)
    svg.append("</svg>")
    output = ROOT / "runart-comparison.svg"
    output.write_text("\n".join(svg) + "\n")
    print(f"Generated {output.relative_to(ROOT.parent.parent)}")
    print(f"Validated {len(checkpoints)} checkpoints x {len(targets)} targets")
    print(f"Reference totals: {source_totals}; local totals: {own_totals}")


if __name__ == "__main__":
    main()
