"""Self-contained vector report for checkpoint activity comparisons."""

from html import escape
import json
import math

from compare_activity import clock, subtract
from pace_chart import wrap_text


def numeric(value, digits=0, signed=False):
    if value is None:
        return "—"
    rounded = round(value, digits)
    if rounded == 0:
        rounded = 0.0
    return f"{rounded:+.{digits}f}" if signed and rounded else f"{rounded:.{digits}f}"


def time_status(delta: float, segment=False) -> tuple[str, str, str]:
    """Plan minus actual: positive means the recorded runner is ahead."""
    if abs(delta) < .5:
        return "持平 00:00:00", "#626D79", "#F0F2F5"
    if delta > 0:
        return ("本段快 " if segment else "实际领先 ") + clock(delta), "#087F5B", "#EAF6EF"
    return ("本段慢 " if segment else "实际落后 ") + clock(abs(delta)), "#C23B38", "#FCEEEE"


def split_at_zero(points: list[tuple[float, float]]) -> list:
    """Insert exact zero crossings before assigning a status to each line piece."""
    pieces = []
    for start, end in zip(points, points[1:]):
        if start[1] * end[1] < 0:
            crossing = (start[0] + (end[0] - start[0]) * start[1] / (start[1] - end[1]), 0)
            pieces.extend(((start, crossing), (crossing, end)))
        else:
            pieces.append((start, end))
    return pieces


def axis_limit(values: list[float]) -> float:
    half_minutes = max(1, max(abs(value) for value in values) / 120)
    magnitude = 10 ** math.floor(math.log10(half_minutes))
    step = next(factor * magnitude for factor in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10)
                if factor * magnitude >= half_minutes)
    return step * 120


def minute_delta_label(delta: float) -> str:
    if abs(delta) < .5:
        return "持平"
    if abs(delta) < 6:
        return ("快" if delta > 0 else "慢") + str(math.floor(abs(delta) + .5)) + "秒"
    return numeric(delta / 60, 1, signed=True)


def render_svg(comparison: dict) -> str:
    plan, activity = comparison["plan"], comparison["activity"]
    cps, schedules = comparison["checkpoints"], plan["schedules"]
    count, targets = len(cps) - 1, plan["targets_seconds"]
    width = max(2720, 560 + 500 * (len(targets) + 1))
    table_width = width - 128
    row_height = 72
    panel_columns = min(3, len(targets))
    panel_rows = math.ceil(len(targets) / panel_columns)
    panel_height, panel_gap, panel_top = 840, 24, 410
    time_heading = panel_top + panel_rows * (panel_height + panel_gap) + 36
    table1 = time_heading + 116
    checkpoint_height = 128
    terrain_heading = table1 + count * checkpoint_height + 62
    table2 = terrain_heading + 100
    footer_y = table2 + count * row_height + 62
    ink, muted = "#202A35", "#626D79"
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

    def path(points, color, line_width=3, dash=""):
        d = " ".join(f'{"M" if i == 0 else "L"}{x:.3f} {y:.3f}'
                     for i, (x, y) in enumerate(points))
        attrs = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{line_width}" '
                     f'stroke-linecap="round" stroke-linejoin="round"{attrs}/>')

    def focus_group(identifier, description, css_class="inspectable"):
        parts.append(f'<g id="{identifier}" class="{css_class}" tabindex="0" '
                     f'aria-label="{escape(description, quote=True)}">')
        parts.append(f"<title>{escape(description)}</title>")

    def paired(x, y, value, delta, digits=0):
        text(x, y + 27, numeric(value, digits), 26, anchor="middle")
        delta_text = "—" if delta is None else numeric(delta, digits, signed=True)
        text(x, y + 54, f"({delta_text})", 20, muted, anchor="middle")

    def row(y, index):
        rect(64, y, table_width, row_height - 2, "#ffffff" if index % 2 else "#F2F4F7", 3)

    cell_width = (width - 704) / (len(targets) + 1)
    actual_x = 640 + cell_width / 2
    plan_xs = [actual_x + cell_width * (j + 1) for j in range(len(targets))]

    def time_headers(y, first):
        text(78, y, first, 22, muted, 600)
        text(484, y, "时间口径", 22, muted, 600)
        text(actual_x, y, "佳明实际", 24, ink, 700, "middle")
        for x, target in zip(plan_xs, targets):
            text(x, y, "方案 " + clock(target).removesuffix(":00"), 24, ink, 600, "middle")

    rect(0, 0, width, 10000, "#F7F8FA")
    rect(0, 0, width, 6, ink)
    text(64, 78, plan["name"], 45, weight=700)
    text(width - 64, 76, "佳明实际 × 仓库方案", 30, anchor="end")
    label(64, 125, f'{activity["start_time"][:10]} · {activity["activity_name"]}', units=140, size=24)
    card_width = (table_width - 72) / 4
    rect(64, 157, card_width, 126, "#ffffff", 13)
    text(88, 191, "实际完赛时间", 21, muted)
    text(88, 242, clock(activity["totals"]["elapsed_seconds"]), 40, ink, 700)
    text(88, 269, "经过时间 · 包含停留", 18, muted)
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
             23, muted, anchor="end")

    cumulative = [[predicted["arrival_seconds"] - actual["elapsed_seconds"]
                   for predicted, actual in zip(schedule["checkpoints"], cps)]
                  for schedule in schedules]
    segment_deltas = [[segment["plans"][j]["delta_seconds"] for segment in comparison["segments"]]
                      for j in range(len(targets))]
    cumulative_limit = axis_limit([value for values in cumulative for value in values])
    segment_limit = axis_limit([value for values in segment_deltas for value in values])
    panel_width = (table_width - panel_gap * (panel_columns - 1)) / panel_columns
    labels = ["起点"] + [cp["name"].split("-")[0].split("－")[0] for cp in cps[1:-1]] + ["终点"]
    parts.append('<g id="time-advantage">')
    text(64, 335, "01  实际领先，还是落后？", 30, weight=700)
    text(64, 377, "以各目标方案为基准 · 零线 = 与计划一致 · 同类图使用相同刻度", 22, muted)
    text(width - 64, 377, "绿色 ↑ 领先 / 本段快     红色 ↓ 落后 / 本段慢", 23, ink, 600, "end")

    def axes(left, right, top, height, limit, kind):
        zero, scale = top + height / 2, height / (2 * limit)
        parts.append(f'<g data-kind="{kind}" data-x-min="{left}" data-x-max="{right}" '
                     f'data-zero-y="{zero}" data-pixels-per-second="{scale}" data-limit-seconds="{limit}">')
        rect(left, top, right - left, height / 2, "#F3FAF6")
        rect(left, zero, right - left, height / 2, "#FEF5F5")
        for fraction in (1, .5, 0, -.5, -1):
            y = zero - fraction * height / 2
            path([(left, y), (right, y)], "#A1ABB5" if fraction == 0 else "#E0E6E9",
                 2 if fraction == 0 else 1, "" if fraction == 0 else "4 5")
            if fraction == 0:
                parts[-1] = parts[-1].replace("/>", ' data-role="zero-line"/>')
            text(left - 12, y + 6, "0" if fraction == 0 else numeric(fraction * limit / 60, signed=True),
                 18, muted, anchor="end")
        text(left, top - 14, "分钟", 17, muted)
        return zero, scale

    for j, target in enumerate(targets):
        column, row_index = j % panel_columns, j // panel_columns
        left = 64 + column * (panel_width + panel_gap)
        top = panel_top + row_index * (panel_height + panel_gap)
        parts.append(f'<g class="target-panel" data-target-seconds="{target}" '
                     f'data-column="{column}" data-row="{row_index}">')
        rect(left, top, panel_width, panel_height, "#FFFFFF", 12)
        text(left + 28, top + 43, "对照 " + clock(target).removesuffix(":00") + " 方案", 28, weight=700)
        status, color, tint = time_status(target - activity["totals"]["elapsed_seconds"])
        rect(left + 24, top + 63, panel_width - 48, 58, tint, 6)
        text(left + 40, top + 101, status, 30, color, 700)
        parts[-1] = parts[-1].replace("<text ", '<text class="finish-status" ')
        text(left + panel_width - 40, top + 99, "完赛", 20, color, anchor="end")
        text(left + 28, top + 164, "累计到站差距", 24, weight=650)
        text(left + panel_width - 28, top + 164, "上方领先 · 下方落后", 19, muted, anchor="end")
        x0, x1 = left + 80, left + panel_width - 32
        plot_top, plot_height = top + 202, 280
        zero, scale = axes(x0, x1, plot_top, plot_height, cumulative_limit, "cumulative")
        positions = [x0 + cp["distance_m"] / plan["route"]["distance_m"] * (x1 - x0)
                     for cp in plan["checkpoints"]]
        raw_points = list(zip(positions, cumulative[j]))
        for start, end in split_at_zero(raw_points):
            color = time_status((start[1] + end[1]) / 2)[1]
            points = [(x, zero - value * scale) for x, value in (start, end)]
            area = " ".join(f'{"M" if i == 0 else "L"}{x:.3f} {y:.3f}'
                            for i, (x, y) in enumerate([(start[0], zero), *points, (end[0], zero)]))
            parts.append(f'<path d="{area} Z" fill="{color}" opacity=".12"/>')
            path(points, color, 4)
        previous_label = -math.inf
        for i, (x, delta) in enumerate(raw_points):
            status, color, _ = time_status(delta)
            tip = (f'{cps[i]["name"]}：{status}；实际 {clock(cps[i]["elapsed_seconds"])}；'
                   f'计划 {clock(schedules[j]["checkpoints"][i]["arrival_seconds"])}')
            parts.append(f'<circle class="delta-point" tabindex="0" cx="{x:.3f}" cy="{zero - delta * scale:.3f}" '
                         f'r="5" fill="{color}" stroke="#FFFFFF" stroke-width="2" data-delta-seconds="{delta}" '
                         f'aria-label="{escape(tip, quote=True)}"><title>{escape(tip)}</title></circle>')
            if i == count or x - previous_label > 46 and (i == 0 or x1 - x > 46):
                text(x, plot_top + plot_height + 28, labels[i][:10], 17, muted, anchor="middle")
                text(x, plot_top + plot_height + 49, f'{plan["checkpoints"][i]["distance_m"] / 1000:.1f}',
                     15, muted, anchor="middle")
                previous_label = x
        text(x1, plot_top + plot_height + 74, "赛道累计距离 / km →", 17, muted, anchor="end")
        parts.append("</g>")

        text(left + 28, top + 582, "每段快 / 慢了多少", 24, weight=650)
        text(left + panel_width - 28, top + 582, "上方快 · 下方慢", 19, muted, anchor="end")
        bar_top, bar_height = top + 620, 160
        zero, scale = axes(x0, x1, bar_top, bar_height, segment_limit, "segment")
        slot = (x1 - x0) / count
        bar_width = min(38, slot * .55)
        for i, delta in enumerate(segment_deltas[j], 1):
            x = x0 + (i - .5) * slot
            status, color, _ = time_status(delta, True)
            segment = comparison["segments"][i - 1]
            tip = (f'{segment["from_name"]} → {segment["to_name"]}：{status}；'
                   f'实际 {clock(segment["actual_seconds"])}；计划 {clock(segment["plans"][j]["seconds"])}')
            focus_group(f"bar-{j}-{i}", tip)
            parts.append(f'<rect x="{x - bar_width / 2:.3f}" y="{zero - max(0, delta) * scale:.3f}" '
                         f'width="{bar_width:.3f}" height="{abs(delta) * scale:.3f}" fill="{color}" '
                         f'data-delta-seconds="{delta}"/>')
            text(x, zero - delta * scale + (-9 if delta >= 0 else 20),
                 minute_delta_label(delta), min(18, slot / 3), color, 600, "middle")
            text(x, bar_top + bar_height + 30, labels[i][:10], min(17, slot / 3),
                 muted, anchor="middle")
            parts.append("</g>")
        parts.append("</g></g>")
    parts.append("</g>")

    parts.append('<g id="checkpoint-times">')
    text(64, time_heading, "02  逐站时间明细", 28, weight=700)
    text(64, time_heading + 40, "先读佳明实际，再看目标方案；彩色文字直接说明实际领先 / 落后、本段快 / 慢。", 22, muted)
    time_headers(table1 - 24, "到达站点 / 来自上一站")
    for i, segment in enumerate(comparison["segments"], 1):
        y = table1 + (i - 1) * checkpoint_height
        description = (f'{segment["from_name"]} → {segment["to_name"]}；'
                       f'实际累计 {clock(cps[i]["elapsed_seconds"])}；'
                       f'本段 {clock(segment["actual_seconds"])}，包含停留。')
        focus_group(f"checkpoint-{i}", description)
        rect(64, y, table_width, checkpoint_height - 4, "#ffffff" if i % 2 else "#F2F4F7", 5)
        parts[-1] = parts[-1].replace("<rect ", '<rect class="row-bg" ')
        label(84, y + 42, cps[i]["name"], units=32)
        label(84, y + 91, "来自 " + cps[i - 1]["name"], units=34, size=18)
        path([(464, y + 16), (464, y + 108)], "#E2E6EB", 1)
        path([(484, y + 62), (width - 88, y + 62)], "#E2E6EB", 1)
        for row_id, offset, heading, actual, predictions in (
            ("time-cp", 0, "累计到站", cps[i]["elapsed_seconds"],
             [s["checkpoints"][i]["arrival_seconds"] for s in schedules]),
            ("segment", 62, "本段耗时", segment["actual_seconds"],
             [entry["seconds"] for entry in segment["plans"]]),
        ):
            parts.append(f'<g id="{row_id}-{i}">')
            text(484, y + offset + 38, heading, 21, muted)
            text(actual_x, y + offset + 38, clock(actual), 26, ink, 650, "middle")
            for x, predicted in zip(plan_xs, predictions):
                status, color, tint = time_status(predicted - actual, row_id == "segment")
                rect(x - cell_width / 2 + 8, y + offset + 3, cell_width - 16, 56, tint, 5)
                parts[-1] = parts[-1].replace("<rect ", '<rect class="status-bg" ')
                text(x, y + offset + 26, clock(predicted), 26, anchor="middle")
                text(x, y + offset + 51, status, 21, color, 650, "middle")
                parts[-1] = parts[-1].replace("<text ", f'<text data-delta-seconds="{predicted - actual}" ')
            parts.append("</g>")
        parts.append("</g>")
    parts.append("</g>")

    parts.append('<g id="terrain">')
    text(64, terrain_heading, "03  地形数据", 28, weight=700)
    text(width - 64, terrain_heading, "佳明在前；仓库括号内：仓库 − 佳明", 22, muted, anchor="end")
    terrain_width = (width - 548) / 3
    for j, heading in enumerate(("累计距离 / km", "本段爬升 / m", "本段下降 / m")):
        left = 484 + j * terrain_width
        text(left + terrain_width / 2, terrain_heading + 42, heading, 24, weight=600, anchor="middle")
        text(left + terrain_width / 4, terrain_heading + 74, "佳明", 22, ink, 600, anchor="middle")
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
            text(left + terrain_width / 4, y + 42, numeric(a, digits), 24, ink, 650, "middle")
            paired(left + terrain_width * .75, y, p, subtract(p, a), digits=digits)
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
        "time_display": "actual ahead/faster when plan minus actual is positive; behind/slower when negative",
        "checkpoint_matches": [
            {"id": cp["id"], "offset_m": cp["offset_m"], "method": cp["match_method"]}
            for cp in cps
        ],
    }
    heading = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">\n'
        f'<title id="title">{escape(plan["name"])}：佳明实际与仓库方案对比</title>\n'
        '<desc id="description">先按目标展示实际领先或落后的累计差距曲线和本段快慢柱图，再列出逐站时间和地形数据。'
        '绿色与零线上方表示实际领先或本段更快，红色与下方表示实际落后或本段更慢；文字直接标注状态。'
        '地形括号为仓库减佳明。时间含停留，差值先计算再取整。</desc>\n'
        '<metadata>' + escape(json.dumps(metadata, ensure_ascii=False)) + '</metadata>\n'
        '<style>text{font-family:"PingFang SC","Noto Sans CJK SC","Microsoft YaHei",sans-serif;'
        'font-variant-numeric:tabular-nums}'
        '.inspectable,.delta-point{outline:none}'
        '.inspectable:hover .row-bg,.inspectable:focus .row-bg{fill:#E9EDF2;stroke:#8995A3;stroke-width:2}'
        '.delta-point:hover,.delta-point:focus{r:8;stroke:#202A35}'
        '.inspectable:hover rect[data-delta-seconds],.inspectable:focus rect[data-delta-seconds]'
        '{stroke:#202A35;stroke-width:2}'
        '#data-notes:focus text{text-decoration:underline}'
        '</style>\n'
    )
    parts[0] = parts[0].replace('height="10000"', f'height="{height}"')
    return heading + "\n".join(parts) + "\n</svg>\n"
