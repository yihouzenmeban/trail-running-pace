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
    table1 = 450
    checkpoint_height = 128
    terrain_heading = table1 + count * checkpoint_height + 62
    table2 = terrain_heading + 100
    curve_heading = table2 + count * row_height + 62
    legend_rows = math.ceil((len(targets) + 1) / 6)
    plot_top = curve_heading + 100 + legend_rows * 40
    footer_y = plot_top + 540
    ink, muted, teal, rust = "#203c46", "#627780", "#126b70", "#aa472e"
    series_colors = ("#126b70", "#486aa6", "#9a6c1d", "#52694b", "#535b63", "#994d65")
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

    def focus_group(identifier, description, css_class="inspectable"):
        parts.append(f'<g id="{identifier}" class="{css_class}" tabindex="0" '
                     f'aria-label="{escape(description, quote=True)}">')
        parts.append(f"<title>{escape(description)}</title>")

    def delta_color(value):
        return muted if value is None or value == 0 else teal if value < 0 else rust

    def paired(x, y, value, delta, is_time=False, digits=0):
        text(x, y + 27, clock(value) if is_time else numeric(value, digits), 26, anchor="middle")
        delta_text = ("—" if delta is None else time_delta(delta) if is_time
                      else numeric(delta, digits, signed=True))
        text(x, y + 54, f"({delta_text})", 20, delta_color(delta), anchor="middle")

    def row(y, index):
        rect(64, y, table_width, row_height - 2, "#ffffff" if index % 2 else "#eaf0ed", 3)

    cell_width = (width - 704) / (len(targets) + 1)
    actual_x = 640 + cell_width / 2
    plan_xs = [actual_x + cell_width * (j + 1) for j in range(len(targets))]

    def time_headers(y, first):
        text(78, y, first, 22, muted, 600)
        text(484, y, "时间口径", 22, muted, 600)
        text(actual_x, y, "佳明实际", 24, rust, 600, "middle")
        for x, target in zip(plan_xs, targets):
            text(x, y, "方案 " + clock(target).removesuffix(":00"), 24, teal, 600, "middle")

    rect(0, 0, width, 10000, "#f5f4ef")
    rect(0, 0, width, 10, teal)
    text(64, 78, plan["name"], 45, weight=700)
    text(width - 64, 76, "佳明实际 × 仓库方案", 30, anchor="end")
    label(64, 125, f'{activity["start_time"][:10]} · {activity["activity_name"]}', units=140, size=24)
    card_width = (table_width - 72) / 4
    rect(64, 157, card_width, 126, ink, 13)
    text(88, 191, "实际完赛时间", 21, "#c8dbde")
    text(88, 242, clock(activity["totals"]["elapsed_seconds"]), 40, "#ffffff", 650)
    text(88, 269, "经过时间 · 包含停留", 18, "#c8dbde")
    for j, (title, key, scale, unit, digits) in enumerate((
        ("全程距离", "distance_m", 1000, "km", 2),
        ("累计爬升", "ascent_m", 1, "m", 0),
        ("累计下降", "descent_m", 1, "m", 0),
    )):
        x = 64 + (j + 1) * (card_width + 24)
        a = activity["totals"][key]
        a = None if a is None else a / scale
        p = plan["route"][key] / scale
        rect(x, 157, card_width, 126, "#ffffff", 13)
        text(x + 24, 191, title, 21, muted)
        text(x + 24, 238, f"{numeric(a, digits)} / {numeric(p, digits)} {unit}", 30, weight=650)
        text(x + 24, 269, "佳明 / 仓库", 18, muted)
        delta = subtract(p, a)
        text(x + card_width - 24, 269, numeric(delta, digits, signed=True) + " " + unit,
             23, delta_color(delta), anchor="end")

    parts.append('<g id="checkpoint-times">')
    text(64, 335, "01  逐站时间对比", 28, weight=700)
    text(64, 375, "每站两行：累计到站 / 本段耗时。括号为方案 − 佳明，负值表示方案更早或本段更短。", 22, muted)
    time_headers(426, "到达站点 / 来自上一站")
    for i, segment in enumerate(comparison["segments"], 1):
        y = table1 + (i - 1) * checkpoint_height
        description = (f'{segment["from_name"]} → {segment["to_name"]}；'
                       f'实际累计 {clock(cps[i]["elapsed_seconds"])}；'
                       f'本段 {clock(segment["actual_seconds"])}，包含停留。')
        focus_group(f"checkpoint-{i}", description)
        rect(64, y, table_width, checkpoint_height - 4, "#ffffff" if i % 2 else "#eaf0ed", 5)
        parts[-1] = parts[-1].replace("<rect ", '<rect class="row-bg" ')
        label(84, y + 42, cps[i]["name"], units=32)
        label(84, y + 91, "来自 " + cps[i - 1]["name"], units=34, size=18)
        path([(464, y + 16), (464, y + 108)], "#d4dfdc", 1)
        path([(484, y + 62), (width - 88, y + 62)], "#dce5e1", 1)
        for row_id, offset, heading, actual, predictions in (
            ("time-cp", 0, "累计到站", cps[i]["elapsed_seconds"],
             [s["checkpoints"][i]["arrival_seconds"] for s in schedules]),
            ("segment", 62, "本段耗时", segment["actual_seconds"],
             [entry["seconds"] for entry in segment["plans"]]),
        ):
            parts.append(f'<g id="{row_id}-{i}">')
            text(484, y + offset + 38, heading, 21, muted)
            text(actual_x, y + offset + 38, clock(actual), 26, rust, 600, "middle")
            for x, predicted in zip(plan_xs, predictions):
                paired(x, y + offset, predicted, predicted - actual, is_time=True)
            parts.append("</g>")
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
        focus_group(f"terrain-cp-{i}", f'{cps[i]["name"]}：累计距离，本段爬升与下降；括号为仓库减佳明。')
        row(y, i)
        parts[-1] = parts[-1].replace("<rect ", '<rect class="row-bg" ')
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

    max_hours = max(targets + [activity["totals"]["elapsed_seconds"]]) / 3600
    tick = max(1, math.ceil(max_hours / 6))
    ceiling = math.ceil(max_hours / tick) * tick
    plot_left, plot_right = 150, width - 100
    bottom = plot_top + 400
    parts.append(f'<g id="time-curves" data-x-min="{plot_left}" data-x-max="{plot_right}" '
                 f'data-y-top="{plot_top}" data-y-bottom="{bottom}" data-max-seconds="{ceiling * 3600}">')
    text(64, curve_heading, "03  全程时间走势", 28, weight=700)
    text(64, curve_heading + 40, "横轴按赛道累计距离对齐 CP；同一位置比较实际与各目标的累计经过时间。", 22, muted)
    labels = ["起点"] + [cp["name"].split("-")[0].split("－")[0] for cp in cps[1:-1]] + ["终点"]
    positions = [plot_left + cp["distance_m"] / plan["route"]["distance_m"] * (plot_right - plot_left)
                 for cp in plan["checkpoints"]]
    for hour in range(0, ceiling + 1, tick):
        y = bottom - hour / ceiling * 400
        path([(plot_left, y), (plot_right, y)], "#dde5e6", 2)
        text(plot_left - 18, y + 7, f"{hour} h", 18, muted, anchor="end")
    previous_label_x = -math.inf
    for i, (x, cp_label) in enumerate(zip(positions, labels)):
        path([(x, plot_top), (x, bottom)], "#e4e9e6", 1)
        if i == count or x - previous_label_x > 90 and (i == 0 or plot_right - x > 90):
            text(x, bottom + 32, cp_label[:12], 19, muted, anchor="middle")
            text(x, bottom + 58, f'{plan["checkpoints"][i]["distance_m"] / 1000:.1f} km',
                 16, muted, anchor="middle")
            previous_label_x = x
    series_data = [
        (f"方案 {clock(targets[j]).removesuffix(':00')}",
         [cp["arrival_seconds"] for cp in schedule["checkpoints"]],
         series_colors[j % len(series_colors)], "repository", targets[j])
        for j, schedule in enumerate(schedules)
    ] + [("佳明实际", [cp["elapsed_seconds"] for cp in cps], rust, "garmin", None)]
    for j, (name, values, color, series, target) in enumerate(series_data):
        focus_group(f"curve-{j}", name + "：各 CP 累计经过时间", "curve")
        lx = 78 + (j % 6) * (table_width / 6)
        ly = curve_heading + 80 + (j // 6) * 40
        path([(lx, ly - 8), (lx + 45, ly - 8)], color, 4, series != "garmin")
        text(lx + 60, ly, name, 22, color)
        points = [(x, bottom - value / (ceiling * 3600) * 400) for x, value in zip(positions, values)]
        path(points, color, 4 if series == "garmin" else 3, series != "garmin", series)
        if target is not None:
            parts[-1] = parts[-1].replace("/>", f' data-target-seconds="{target}"/>')
        for i, (x, y) in enumerate(points):
            tip = f'{cps[i]["name"]} · {name}：{clock(values[i])}'
            if target is not None:
                tip += "；方案 − 佳明：" + time_delta(values[i] - cps[i]["elapsed_seconds"])
            parts.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="5" fill="{color}">'
                         f'<title>{escape(tip)}</title></circle>')
        parts.append("</g>")
    parts.append("</g>")

    lap_totals = activity.get("lap_totals") or {}
    notes = [
        f'来源：路线与现有配速模型；实际活动 {activity["start_time"][:10]}「{activity["activity_name"]}」。汇总来源：{activity["totals_source"]}。',
        "CP 经过时间由原始 FIT 轨迹投影或明确指定的实际耗时得到，包含停留，非官方打卡；无法可靠拆分站内停留。",
        "佳明分站累计爬升、下降按 FIT 逐圈距离插值；本段值为相邻站累计值之差。终点使用活动汇总，未按比例调整。",
        f'FIT 逐圈爬升 / 下降：{numeric(lap_totals.get("ascent_m"))} / {numeric(lap_totals.get("descent_m"))} m；'
        f'汇总：{numeric(activity["totals"]["ascent_m"])} / {numeric(activity["totals"]["descent_m"])} m。'
        "差值使用未取整原值；分段显示值之和可能有取整误差；缺失值为 —。",
    ]
    if comparison["warnings"]:
        notes += ["数据提示：" + warning for warning in comparison["warnings"]]
    focus_group("data-notes", "\n".join(notes))
    text(64, footer_y, "口径：时间包含停留，CP 非官方打卡；本段爬升 / 下降由 FIT 逐圈累计估算值相减，未知为 —。", 20, muted)
    text(64, footer_y + 32, "差值先计算再取整；方案停留计入下一段。数据来源与匹配详情可悬停此处查看，也保存在 SVG 元数据中。", 20, muted)
    parts.append("</g>")
    height = footer_y + 70
    metadata = {
        "route_sha256": plan["source"]["sha256"], "config_sha256": comparison.get("config_sha256"),
        "activity_id": activity["activity_id"], "activity_date": activity["start_time"],
        "targets_seconds": targets, **activity.get("source", {}), **comparison["semantics"],
        "warnings": comparison["warnings"], "passage_overrides": comparison["passage_overrides"],
        "data_notes": notes,
        "checkpoint_matches": [
            {"id": cp["id"], "offset_m": cp["offset_m"], "method": cp["match_method"]}
            for cp in cps
        ],
    }
    heading = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">\n'
        f'<title id="title">{escape(plan["name"])}：佳明实际与仓库方案对比</title>\n'
        '<desc id="description">逐站并排比较累计到站与本段耗时，随后展示地形数据和共用坐标的全程时间走势。'
        '括号内差值为仓库减佳明，使用未取整数据计算。独立打开可悬停或聚焦站点与曲线查看。</desc>\n'
        '<metadata>' + escape(json.dumps(metadata, ensure_ascii=False)) + '</metadata>\n'
        '<style>text{font-family:"PingFang SC","Noto Sans CJK SC","Microsoft YaHei",sans-serif;'
        'font-variant-numeric:tabular-nums}'
        '.inspectable,.curve{outline:none}'
        '.inspectable:hover .row-bg,.inspectable:focus .row-bg{fill:#deebe5;stroke:#126b70;stroke-width:2}'
        '.curve:hover path[data-series],.curve:focus path[data-series]{stroke-width:6}'
        '.curve:hover circle,.curve:focus circle{r:7}'
        '#data-notes:focus text{text-decoration:underline}'
        '</style>\n'
    )
    parts[0] = parts[0].replace('height="10000"', f'height="{height}"')
    return heading + "\n".join(parts) + "\n</svg>\n"
