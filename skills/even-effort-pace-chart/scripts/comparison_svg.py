"""Self-contained vector report for checkpoint activity comparisons."""

from html import escape
import json
import math

from compare_activity import clock, subtract, time_delta
from pace_chart import wrap_text


def numeric(value, digits=0, signed=False):
    if value is None:
        return "—"
    rounded = round(value, digits)
    if rounded == 0:
        rounded = 0.0
    return f"{rounded:+.{digits}f}" if signed and rounded else f"{rounded:.{digits}f}"


def render_svg(comparison: dict) -> str:
    plan, activity = comparison["plan"], comparison["activity"]
    cps, schedules = comparison["checkpoints"], plan["schedules"]
    count, targets = len(cps) - 1, plan["targets_seconds"]
    width = max(2720, 560 + 500 * (len(targets) + 1))
    table_width = width - 128
    row_height = 72
    table1 = 430
    terrain_heading = table1 + count * row_height + 62
    table2 = terrain_heading + 100
    segment_heading = table2 + count * row_height + 62
    table3 = segment_heading + 140
    curve_heading = table3 + count * row_height + 62
    panels_per_row = min(3, len(targets))
    plot_rows = math.ceil(len(targets) / panels_per_row)
    footer_y = curve_heading + 80 + plot_rows * 440 + 30
    ink, muted, teal, rust = "#203c46", "#627780", "#126b70", "#aa472e"
    parts = []

    def rect(x, y, w, h, fill, radius=0):
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}"/>')

    def text(x, y, value, size=22, color=ink, weight=400, anchor="start"):
        parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
                     f'font-weight="{weight}" text-anchor="{anchor}">{escape(str(value))}</text>')

    def label(x, y, value, units=36, size=23):
        lines = wrap_text(value, units)
        for i, line in enumerate(lines):
            text(x, y + (i - (len(lines) - 1) / 2) * (size + 3), line, size)

    def path(points, color, line_width=3, dashed=False, series=None):
        d = " ".join(f'{"M" if i == 0 else "L"}{x:.3f} {y:.3f}'
                     for i, (x, y) in enumerate(points))
        attrs = (' stroke-dasharray="9 6"' if dashed else "")
        if series:
            attrs += f' data-series="{series}"'
        parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{line_width}"{attrs}/>')

    def delta_color(value):
        return muted if value is None or value == 0 else teal if value < 0 else rust

    def paired(x, y, value, delta, is_time=False, digits=0):
        text(x, y + 27, clock(value) if is_time else numeric(value, digits), 26, anchor="middle")
        delta_text = ("—" if delta is None else time_delta(delta) if is_time
                      else numeric(delta, digits, signed=True))
        text(x, y + 54, f"({delta_text})", 20, delta_color(delta), anchor="middle")

    def row(y, index):
        rect(64, y, table_width, row_height - 2, "#ffffff" if index % 2 else "#eaf0ed", 3)

    actual_x = 500 + (width - 564) / (len(targets) + 1) / 2
    cell_width = (width - 564) / (len(targets) + 1)
    plan_xs = [actual_x + cell_width * (j + 1) for j in range(len(targets))]

    def time_headers(y, first):
        text(78, y, first, 22, muted, 600)
        text(actual_x, y, "佳明实际", 24, rust, 600, "middle")
        for x, target in zip(plan_xs, targets):
            text(x, y, "仓库 " + clock(target), 24, teal, 600, "middle")

    rect(0, 0, width, 10000, "#f5f4ef")
    rect(0, 0, width, 10, teal)
    text(64, 78, plan["name"], 45, weight=700)
    text(width - 64, 76, "佳明实际 × 仓库方案", 30, anchor="end")
    label(64, 125, f'{activity["start_time"][:10]} · {activity["activity_name"]}', units=140, size=24)
    card_width = (table_width - 48) / 3
    for j, (title, key, scale, unit, digits) in enumerate((
        ("全程距离", "distance_m", 1000, "km", 2),
        ("累计爬升", "ascent_m", 1, "m", 0),
        ("累计下降", "descent_m", 1, "m", 0),
    )):
        x = 64 + j * (card_width + 24)
        a = activity["totals"][key]
        a = None if a is None else a / scale
        p = plan["route"][key] / scale
        rect(x, 157, card_width, 126, "#ffffff", 13)
        text(x + 24, 191, title, 21, muted)
        text(x + 24, 242, f"{numeric(a, digits)} / {numeric(p, digits)} {unit}", 36, weight=650)
        text(x + 24, 269, "佳明 / 仓库", 18, muted)
        delta = subtract(p, a)
        text(x + card_width - 24, 269, numeric(delta, digits, signed=True) + " " + unit,
             23, delta_color(delta), anchor="end")

    parts.append('<g id="cumulative-times">')
    text(64, 331, "01  各站累计经过时间", 28, weight=700)
    text(64, 371, "时间包含停留；括号内：方案 − 佳明。负值表示更早，正值表示更晚。", 22, muted)
    text(width - 64, 371, "佳明全程：" + clock(activity["totals"]["elapsed_seconds"]),
         24, rust, 600, "end")
    time_headers(412, "站点")
    for i in range(1, count + 1):
        y = table1 + (i - 1) * row_height
        parts.append(f'<g id="time-cp-{i}">')
        row(y, i)
        label(78, y + 42, cps[i]["name"])
        actual = cps[i]["elapsed_seconds"]
        text(actual_x, y + 42, clock(actual), 26, rust, 600, "middle")
        for x, schedule in zip(plan_xs, schedules):
            predicted = schedule["checkpoints"][i]["arrival_seconds"]
            paired(x, y, predicted, predicted - actual, is_time=True)
        parts.append("</g>")
    parts.append("</g>")

    parts.append('<g id="terrain">')
    text(64, terrain_heading, "02  地形数据", 28, weight=700)
    text(width - 64, terrain_heading, "佳明在前；仓库括号内：仓库 − 佳明", 22, muted, anchor="end")
    terrain_width = (width - 548) / 3
    for j, heading in enumerate(("累计距离 / km", "本段爬升 / m", "本段下降 / m")):
        left = 484 + j * terrain_width
        text(left + terrain_width / 2, terrain_heading + 42, heading, 24, weight=600, anchor="middle")
        text(left + terrain_width / 4, terrain_heading + 74, "佳明", 22, rust, anchor="middle")
        text(left + terrain_width * .75, terrain_heading + 74, "仓库", 22, muted, anchor="middle")
    text(78, terrain_heading + 74, "站点", 22, muted, 600)
    for i, metrics in enumerate(comparison["terrain"], 1):
        y = table2 + (i - 1) * row_height
        parts.append(f'<g id="terrain-cp-{i}">')
        row(y, i)
        label(78, y + 42, cps[i]["name"])
        for j, key in enumerate(("distance_m", "ascent_m", "descent_m")):
            left = 484 + j * terrain_width
            scale, digits = (1000, 2) if j == 0 else (1, 0)
            a, p = metrics["actual_" + key], metrics["planned_" + key]
            a, p = (None if a is None else a / scale), p / scale
            text(left + terrain_width / 4, y + 42, numeric(a, digits), 24, rust, 600, "middle")
            paired(left + terrain_width * .75, y, p, subtract(p, a), digits=digits)
        parts.append("</g>")
    parts.append("</g>")

    parts.append('<g id="segment-times">')
    text(64, segment_heading, "03  相邻站之间耗时", 28, weight=700)
    text(64, segment_heading + 40, "相邻站累计经过时间相减，包含途中停留；方案包括上一站配置的停留。", 22, muted)
    text(64, segment_heading + 74, "括号内：方案 − 佳明。负值表示本段方案用时更短，正值表示更长。", 22, muted)
    time_headers(segment_heading + 120, "赛段")
    for i, segment in enumerate(comparison["segments"], 1):
        y = table3 + (i - 1) * row_height
        parts.append(f'<g id="segment-{i}">')
        row(y, i)
        label(78, y + 29, segment["from_name"], size=21)
        label(78, y + 57, "→ " + segment["to_name"], size=21)
        text(actual_x, y + 42, clock(segment["actual_seconds"]), 26, rust, 600, "middle")
        for x, entry in zip(plan_xs, segment["plans"]):
            paired(x, y, entry["seconds"], entry["delta_seconds"], is_time=True)
        parts.append("</g>")
    parts.append("</g>")

    parts.append('<g id="time-curves">')
    text(64, curve_heading, "04  实际活动时间对照", 28, weight=700)
    text(64, curve_heading + 40, "各图使用相同的实际经过时间和纵轴尺度；起点均为 00:00:00。", 22, muted)
    path([(width - 710, curve_heading + 32), (width - 665, curve_heading + 32)], teal, dashed=True)
    text(width - 650, curve_heading + 40, "仓库方案", 22, teal)
    path([(width - 360, curve_heading + 32), (width - 315, curve_heading + 32)], rust)
    text(width - 300, curve_heading + 40, "佳明实际", 22, rust)
    max_hours = max(targets + [activity["totals"]["elapsed_seconds"]]) / 3600
    tick = max(1, math.ceil(max_hours / 6))
    ceiling = math.ceil(max_hours / tick) * tick
    panel_width = table_width / panels_per_row
    labels = ["起点"] + [cp["name"].split("-")[0].split("－")[0] for cp in cps[1:-1]] + ["终点"]
    for j, schedule in enumerate(schedules):
        left = 64 + (j % panels_per_row) * panel_width
        top = curve_heading + 100 + (j // panels_per_row) * 440
        plot_left, plot_right = left + 58, left + panel_width - 30
        bottom = top + 318
        parts.append(f'<g id="plot-{j + 1}">')
        text(left, top - 20, clock(targets[j]) + " 方案", 26, weight=650)
        for hour in range(0, ceiling + 1, tick):
            y = bottom - hour / ceiling * 318
            path([(plot_left, y), (plot_right, y)], "#dde5e6", 2)
            text(plot_left - 14, y + 7, f"{hour}h", 18, muted, anchor="end")
        # Thin labels for dense routes; every checkpoint is still present in both curves and tables.
        stride = max(1, math.ceil(len(labels) / max(2, panel_width / 65)))
        for i, cp_label in enumerate(labels):
            if i % stride == 0 or i == count:
                x = plot_left + i * (plot_right - plot_left) / count
                text(x, bottom + 32, cp_label[:10], 18, muted, anchor="middle")
        for values, color, dashed, series in (
            ([c["arrival_seconds"] for c in schedule["checkpoints"]], teal, True, "repository"),
            ([c["elapsed_seconds"] for c in cps], rust, False, "garmin"),
        ):
            points = [(plot_left + i * (plot_right - plot_left) / count,
                       bottom - value / (ceiling * 3600) * 318) for i, value in enumerate(values)]
            path(points, color, 3, dashed, series)
            for x, y in points:
                parts.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="4" fill="{color}"/>')
        parts.append("</g>")
    parts.append("</g>")

    lap_totals = activity.get("lap_totals") or {}
    footer = [
        f'来源：路线与现有配速模型；实际活动 {activity["start_time"][:10]}「{activity["activity_name"]}」。汇总来源：{activity["totals_source"]}。',
        "CP 经过时间由原始 FIT 轨迹投影或明确指定的实际耗时得到，包含停留，非官方打卡；无法可靠拆分站内停留。",
        "佳明分站累计爬升、下降按 FIT 逐圈距离插值；本段值为相邻站累计值之差。终点使用活动汇总，未按比例调整。",
        f'FIT 逐圈爬升 / 下降：{numeric(lap_totals.get("ascent_m"))} / {numeric(lap_totals.get("descent_m"))} m；'
        f'汇总：{numeric(activity["totals"]["ascent_m"])} / {numeric(activity["totals"]["descent_m"])} m。'
        "差值使用未取整原值；分段显示值之和可能有取整误差；缺失值为 —。",
    ]
    if comparison["warnings"]:
        footer += ["数据提示：" + warning for warning in comparison["warnings"]]
    y = footer_y
    for line in footer:
        for wrapped in wrap_text(line, int((width - 128) / 10.5)):
            text(64, y, wrapped, 20, muted)
            y += 30
    height = y + 30
    metadata = {
        "route_sha256": plan["source"]["sha256"], "config_sha256": comparison.get("config_sha256"),
        "activity_id": activity["activity_id"], "activity_date": activity["start_time"],
        "targets_seconds": targets, **activity.get("source", {}), **comparison["semantics"],
        "warnings": comparison["warnings"], "passage_overrides": comparison["passage_overrides"],
        "checkpoint_matches": [
            {"id": cp["id"], "offset_m": cp["offset_m"], "method": cp["match_method"]}
            for cp in cps
        ],
    }
    heading = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">\n'
        f'<title id="title">{escape(plan["name"])}：佳明实际与仓库方案对比</title>\n'
        '<desc id="description">各站累计经过时间、地形数据、相邻站耗时、实际活动时间曲线。'
        '括号内差值为仓库减佳明，使用未取整数据计算。</desc>\n'
        '<metadata>' + escape(json.dumps(metadata, ensure_ascii=False)) + '</metadata>\n'
        '<style>text{font-family:"PingFang SC","Noto Sans CJK SC","Microsoft YaHei",sans-serif;'
        'font-variant-numeric:tabular-nums}</style>\n'
    )
    parts[0] = parts[0].replace('height="10000"', f'height="{height}"')
    return heading + "\n".join(parts) + "\n</svg>\n"
