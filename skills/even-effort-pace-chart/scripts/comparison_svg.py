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


def metric_limit(values: list[float | None]) -> float:
    maximum = max(1, max((abs(v) for v in values if v is not None), default=0))
    magnitude = 10 ** math.floor(math.log10(maximum))
    return next(factor * magnitude for factor in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10)
                if factor * magnitude >= maximum)


def metric_delta_label(delta: float | None) -> str:
    if delta is None:
        return "差值 —"
    rounded = math.floor(abs(delta) + .5)
    if rounded == 0:
        return "差值 0 m"
    return ("仓库多 " if delta > 0 else "仓库少 ") + f"{rounded} m"


def render_svg(comparison: dict) -> str:
    plan, activity = comparison["plan"], comparison["activity"]
    cps, schedules = comparison["checkpoints"], plan["schedules"]
    count, targets = len(cps) - 1, plan["targets_seconds"]
    width = max(2720, 560 + 500 * (len(targets) + 1))
    table_width = width - 128
    row_height = 84
    summary_columns = min(4, len(targets) + 1)
    summary_rows = math.ceil((len(targets) + 1) / summary_columns)
    overview_heading = 157 + summary_rows * 150 + 28
    panel_columns = min(3, len(targets))
    panel_rows = math.ceil(len(targets) / panel_columns)
    panel_height, panel_gap, panel_top = 450, 24, overview_heading + 75
    time_heading = panel_top + panel_rows * (panel_height + panel_gap) + 36
    table1 = time_heading + 116
    checkpoint_height = 92
    terrain_heading = table1 + count * checkpoint_height + 62
    table2 = terrain_heading + 252
    footer_y = table2 + count * row_height + 62
    ink, muted = "#202A35", "#626D79"
    recorded_color, planned_color = "#475569", "#3274AC"
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

    def row(y, index):
        rect(64, y, table_width, row_height - 2, "#ffffff" if index % 2 else "#F2F4F7", 3)

    cell_width = (width - 784) / len(targets)
    actual_x = 588

    rect(0, 0, width, 10000, "#F7F8FA")
    rect(0, 0, width, 6, ink)
    text(64, 78, plan["name"], 45, weight=700)
    text(width - 64, 76, "佳明实际 × 仓库方案", 30, anchor="end")
    label(64, 125, f'{activity["start_time"][:10]} · {activity["activity_name"]}', units=140, size=24)
    card_width = (table_width - 24 * (summary_columns - 1)) / summary_columns
    for j, target in enumerate([None, *targets]):
        x = 64 + (j % summary_columns) * (card_width + 24)
        y = 157 + (j // summary_columns) * 150
        if target is None:
            rect(x, y, card_width, 126, "#ffffff", 13)
            text(x + 24, y + 34, "实际完赛时间", 21, muted)
            text(x + 24, y + 85, clock(activity["totals"]["elapsed_seconds"]), 40, ink, 700)
            text(x + 24, y + 112, "经过时间 · 包含停留", 18, muted)
        else:
            status, color, tint = time_status(target - activity["totals"]["elapsed_seconds"])
            rect(x, y, card_width, 126, tint, 13)
            text(x + 24, y + 34, "对照 " + clock(target).removesuffix(":00") + " 方案", 23, ink, 600)
            text(x + 24, y + 88, status, 31, color, 700)
            parts[-1] = parts[-1].replace("<text ", '<text class="finish-status" ')

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
    text(64, overview_heading, "01  时间表现", 30, weight=700)
    text(64, overview_heading + 42, "累计差距：绿色领先、红色落后；零线 = 与计划一致", 22, muted)
    text(width - 64, overview_heading + 42, "各目标共用刻度 · 悬停点查看累计到站时间", 22, muted, anchor="end")

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
        text(left + 28, top + 43, clock(target).removesuffix(":00") + " 方案 · 累计差距", 26, weight=700)
        text(left + panel_width - 28, top + 43, "上方领先 · 下方落后", 19, muted, anchor="end")
        x0, x1 = left + 80, left + panel_width - 32
        plot_top, plot_height = top + 90, 260
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

        parts.append("</g>")

    parts.append('<g id="checkpoint-times">')
    text(64, time_heading, "每个区间用了多久", 28, weight=700)
    text(64, time_heading + 40, "实际耗时与计划并排；横条越长，快慢差距越大。时间均包含途中停留。", 22, muted)
    text(78, table1 - 24, "到达站点 / 来自上一站", 22, muted, 600)
    text(actual_x, table1 - 24, "佳明实际耗时", 24, ink, 700, "middle")
    for j, target in enumerate(targets):
        center = 720 + cell_width * (j + .5)
        text(center, table1 - 46, "方案 " + clock(target).removesuffix(":00"), 24, ink, 600, "middle")
        text(center, table1 - 18, f"慢 {numeric(segment_limit / 60)} 分 ← 0 → 快 {numeric(segment_limit / 60)} 分",
             18, muted, anchor="middle")
    for i, segment in enumerate(comparison["segments"], 1):
        y = table1 + (i - 1) * checkpoint_height
        description = (f'{segment["from_name"]} → {segment["to_name"]}；'
                       f'实际本段 {clock(segment["actual_seconds"])}，包含停留。')
        focus_group(f"segment-{i}", description, "segment-row inspectable")
        rect(64, y, table_width, checkpoint_height - 4, "#ffffff" if i % 2 else "#F2F4F7", 5)
        parts[-1] = parts[-1].replace("<rect ", '<rect class="row-bg" ')
        label(84, y + 35, cps[i]["name"], units=32)
        label(84, y + 64, "来自 " + cps[i - 1]["name"], units=34, size=18)
        text(actual_x, y + 49, clock(segment["actual_seconds"]), 28, ink, 700, "middle")
        parts[-1] = parts[-1].replace("<text ", '<text data-role="actual-time" ')
        for j, predicted in enumerate(segment["plans"]):
            left = 720 + j * cell_width
            zero, scale = left + cell_width / 2, (cell_width / 2 - 28) / segment_limit
            delta = predicted["delta_seconds"]
            status, color, _ = time_status(delta, True)
            focus_group(f"segment-{i}-plan-{j}", description + f'计划 {clock(predicted["seconds"])}；{status}',
                        "segment-plan inspectable")
            parts[-2] = parts[-2].replace(' tabindex=', f' data-target-seconds="{predicted["target_seconds"]}" '
                                         f'data-zero-x="{zero}" data-pixels-per-second="{scale}" tabindex=')
            text(left + 24, y + 32, clock(predicted["seconds"]), 25, ink, 500)
            parts[-1] = parts[-1].replace("<text ", '<text data-role="planned-time" ')
            text(left + cell_width - 24, y + 32, status, 22, color, 650, "end")
            parts[-1] = parts[-1].replace("<text ", '<text data-role="segment-status" ')
            path([(left + 28, y + 62), (left + cell_width - 28, y + 62)], "#DCE2E8", 2)
            path([(zero, y + 48), (zero, y + 76)], "#8995A3", 2)
            parts.append(f'<rect x="{zero + min(0, delta) * scale:.3f}" y="{y + 54}" '
                         f'width="{abs(delta) * scale:.3f}" height="16" rx="2" fill="{color}" '
                         f'data-delta-seconds="{delta}"/>')
            parts.append("</g>")
        parts.append("</g>")
    parts.append("</g></g>")

    parts.append('<g id="terrain">')
    text(64, terrain_heading, "02  赛道数据对比", 30, weight=700)
    text(width - 64, terrain_heading, "深灰 = 佳明 · 蓝色 = 仓库 · 差值为仓库减佳明", 22, muted, anchor="end")
    terrain_width = (width - 548) / 3
    summary_width = (table_width - 48) / 3
    for j, (title, key, divisor, unit, digits) in enumerate((
        ("全程距离", "distance_m", 1000, "km", 2),
        ("累计爬升", "ascent_m", 1, "m", 0),
        ("累计下降", "descent_m", 1, "m", 0),
    )):
        left = 64 + j * (summary_width + 24)
        a, p = activity["totals"][key], plan["route"][key]
        rect(left, terrain_heading + 24, summary_width, 110, "#ffffff", 10)
        text(left + 24, terrain_heading + 58, title + " · 佳明 / 仓库", 21, muted)
        value = numeric(None if a is None else a / divisor, digits)
        text(left + 24, terrain_heading + 105, f"{value} / {numeric(p / divisor, digits)} {unit}", 30, weight=650)
        text(left + summary_width - 24, terrain_heading + 105, metric_delta_label(subtract(p, a)),
             22, muted, anchor="end")

    distance_limit = metric_limit([subtract(m["planned_distance_m"], m["actual_distance_m"])
                                   for m in comparison["terrain"]])
    elevation_limit = metric_limit([m[source + key] for m in comparison["terrain"]
                                    for source in ("actual_", "planned_") for key in ("ascent_m", "descent_m")])
    for j, title in enumerate(("累计距离差 / m", "本段爬升 / m", "本段下降 / m")):
        left = 484 + j * terrain_width
        text(left + terrain_width / 2, terrain_heading + 177, title, 24, weight=650, anchor="middle")
        if j == 0:
            text(left + 24, table2 - 20, f"仓库少 {numeric(distance_limit)} m", 18, muted)
            text(left + terrain_width / 2, table2 - 20, "0", 18, muted, anchor="middle")
            text(left + terrain_width - 24, table2 - 20, f"仓库多 {numeric(distance_limit)} m", 18, muted, anchor="end")
        else:
            text(left + 24, table2 - 20, "0", 18, muted)
            text(left + terrain_width - 276, table2 - 20, numeric(elevation_limit), 18, muted, anchor="end")
            text(left + terrain_width - 24, table2 - 20, "差值", 18, muted, anchor="end")
    text(78, table2 - 20, "到达站点 / 来自上一站", 22, muted, 600)
    for i, metrics in enumerate(comparison["terrain"], 1):
        y = table2 + (i - 1) * row_height
        focus_group(f"terrain-cp-{i}", f'{cps[i - 1]["name"]} → {cps[i]["name"]}：累计距离，本段爬升与下降。')
        row(y, i)
        parts[-1] = parts[-1].replace("<rect ", '<rect class="row-bg" ')
        label(84, y + 32, cps[i]["name"], units=32)
        label(84, y + 61, "来自 " + cps[i - 1]["name"], units=34, size=18)
        for j, key in enumerate(("distance_m", "ascent_m", "descent_m")):
            left = 484 + j * terrain_width
            a, p = metrics["actual_" + key], metrics["planned_" + key]
            delta = subtract(p, a)
            if key == "distance_m":
                zero = left + terrain_width / 2
                scale = (terrain_width / 2 - 24) / distance_limit
            else:
                zero, scale = left + 24, (terrain_width - 300) / elevation_limit
            focus_group(f"terrain-{key}-{i}", f'{cps[i]["name"]}：{("累计距离", "本段爬升", "本段下降")[j]}；'
                        f'佳明 {numeric(a, 2)} m；仓库 {numeric(p, 2)} m；{metric_delta_label(delta)}')
            parts[-2] = parts[-2].replace(' tabindex=', f' data-metric="{key}" data-zero-x="{zero}" '
                                         f'data-pixels-per-meter="{scale}" '
                                         f'data-actual-available="{str(a is not None).lower()}" tabindex=')
            if key == "distance_m":
                for index, (source, value, color) in enumerate((("actual", a, recorded_color), ("planned", p, planned_color))):
                    value_text = "—" if value is None else numeric(value / 1000, 2) + " km"
                    text(left + 24 + index * 180, y + 30, value_text, 23, color, 600)
                    parts[-1] = parts[-1].replace("<text ", f'<text data-role="{source}-value" ')
                path([(left + 24, y + 60), (left + terrain_width - 24, y + 60)], "#DCE2E8", 2)
                path([(zero, y + 47), (zero, y + 73)], "#8995A3", 2)
                if delta is not None:
                    parts.append(f'<rect x="{zero + min(0, delta) * scale:.3f}" y="{y + 52}" '
                                 f'width="{abs(delta) * scale:.3f}" height="16" rx="2" '
                                 f'fill="{planned_color}" data-delta-m="{delta}"/>')
                text(left + terrain_width - 24, y + 30, metric_delta_label(delta), 21, muted, anchor="end")
            else:
                for index, (source, value, color) in enumerate((("actual", a, recorded_color), ("planned", p, planned_color))):
                    baseline = y + 28 + index * 30
                    if value is not None:
                        parts.append(f'<rect x="{zero:.3f}" y="{baseline - 14}" width="{value * scale:.3f}" '
                                     f'height="16" rx="2" fill="{color}" data-series="{source}" data-value-m="{value}"/>')
                    value_text = "—" if value is None else numeric(value) + " m"
                    text(zero + (0 if value is None else value * scale) + 10, baseline, value_text, 21, color, 600)
                    parts[-1] = parts[-1].replace("<text ", f'<text data-role="{source}-value" ')
                text(left + terrain_width - 24, y + 48, metric_delta_label(delta), 20, muted, anchor="end")
            parts[-1] = parts[-1].replace("<text ", '<text data-role="metric-delta" ')
            parts.append("</g>")
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
        '<desc id="description">时间表现包含累计差距曲线，以及实际、计划耗时与快慢横条合并的区间表；赛道数据展示距离差与分段爬升、下降横条。'
        '绿色表示实际领先或本段更快，红色表示实际落后或本段更慢；累计曲线零线上方领先、下方落后。'
        '横向快慢条左慢右快；地形用深灰表示佳明、蓝色表示仓库。时间含停留，差值先计算再取整。</desc>\n'
        '<metadata>' + escape(json.dumps(metadata, ensure_ascii=False)) + '</metadata>\n'
        '<style>text{font-family:"PingFang SC","Noto Sans CJK SC","Microsoft YaHei",sans-serif;'
        'font-variant-numeric:tabular-nums}'
        '.inspectable,.delta-point{outline:none}'
        '.inspectable:hover .row-bg,.inspectable:focus .row-bg{fill:#E9EDF2;stroke:#8995A3;stroke-width:2}'
        '.delta-point:hover,.delta-point:focus{r:8;stroke:#202A35}'
        '.inspectable:hover rect[data-delta-seconds],.inspectable:focus rect[data-delta-seconds]'
        '{stroke:#202A35;stroke-width:2}'
        '.inspectable:hover > rect[data-delta-m],.inspectable:focus > rect[data-delta-m],'
        '.inspectable:hover > rect[data-series],.inspectable:focus > rect[data-series]'
        '{stroke:#202A35;stroke-width:2}'
        '.inspectable:focus > text{text-decoration:underline}'
        '#data-notes:focus text{text-decoration:underline}'
        '</style>\n'
    )
    parts[0] = parts[0].replace('height="10000"', f'height="{height}"')
    return heading + "\n".join(parts) + "\n</svg>\n"
