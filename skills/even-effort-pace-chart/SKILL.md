---
name: even-effort-pace-chart
description: Convert a GPX or KML race route into an even-effort trail running pace chart with checkpoint splits, elevation profiles, and multiple finish targets. Use when planning race pacing from GPX/KML or generating SVG pace tables, with optional HTML, CSV, and JSON exports.
---

# 耐力学社 Even-Effort Pace Chart Skills

Use `scripts/pace_chart.py` for deterministic, offline calculations and exports. It requires Python 3.10+ and the standard library only. Resolve script paths relative to this file's directory, regardless of the user's working directory.

Read references only as needed, in the user's language: Chinese [configuration](references/configuration.md) / [model](references/model.md), or English [configuration](references/configuration.en.md) / [model](references/model.en.md). Configuration defines fields and CLI contracts; model explains equations and limitations.

Apply **current explicit request > selected configuration > script defaults**. Use a minimal configuration with the requested target, explicit overrides, and confirmed route selections. Omit unspecified fields; preserve valid zeros and `false`. Do not inherit settings from unrelated charts or examples, fill defaults with `null`/empty strings, or ask about optional fields with usable defaults.

Default output is SVG, with segment pace in parentheses and a local 06:00 start. A supplied start time changes `start_time` only. Select `secondary_display: "arrival_time"` or `"equivalent_pace"` only when requested or already selected in the supplied configuration. Legacy `pace_basis: "equivalent"` still selects equivalent pace when `secondary_display` is absent.

## Inspect the route first

```bash
python3 <skill-dir>/scripts/pace_chart.py inspect <race.gpx-or-kml>
```

Read the inspection JSON. Prefer embedded CPs, preserve their names and numbering, and use the returned candidate IDs. Start/finish rows are added automatically. Ask for manual names and cumulative distances only when embedded CPs are absent or unusable.

Review `diagnostics` and warnings for elevation corrections, poor positioning metadata, and distance sensitivity. Trial simplification does not prove drift; never enable `distance_tolerance_m` without an explicit request or selected configuration. Pass the selected processing options to inspection as well as generation, and recheck CP positions after changing distance processing.

Resolve ambiguous inputs before generation:

- Multiple routes: obtain the intended 1-based `track_index`; separate lines are not joined.
- Unrecognized station names: confirm `cp_selection`, rather than treating every landmark as a CP.
- Loops/crossings or offsets over 100 m: confirm the route occurrence with a processed-route `distance_km` override, or confirm `allow_off_route`; do not silently choose the nearest projection.
- KML missing/ground-clamped altitude mode: verify supplied heights before `inspect --use-kml-altitudes` and `use_kml_altitudes: true`. Never fill missing heights with zero. See configuration for supported KML modes and geometry.

## Set targets and assumptions

Obtain the finish target if missing. A `target` expands to five columns with 30-minute spacing; `target_step_minutes` changes the interval. Use `targets` for an exact list, including a single column. When replacing a selected configuration's list with a new central target, remove old `targets`; otherwise the script keeps list precedence and warns. If expansion gives nonpositive durations, obtain an explicit list or interval.

Targets include station rests, which default to zero. Do not invent cutoffs or a race date. Cutoffs are elapsed durations; confirm start/date/rollover when converting clock cutoffs. Missing cutoffs stay unchecked and are omitted from station cells. For manual official-distance mismatches, confirm before using `distance_alignment: "scale"`; see configuration for the threshold and schema.

For example, “生成体感一致配速表，目标完赛时间 5 小时，相邻方案间隔 30 分钟，出发时间早上六点” maps to:

```json
{
  "target": "05:00",
  "target_step_minutes": 30,
  "start_time": "06:00"
}
```

This keeps the default pace display and SVG export. Ascent defaults to the peak/valley threshold method; display smoothing is independent. Consult the model for filtering choices and the explicit `window` alternative. Do not inherit the old 100 m ascent window from examples. Interpolation adds no measurement accuracy; never tune filters or rescale climbs solely to force a platform's total or claim equivalence to RunArt.Net.

## Generate and verify

Write the selected assumptions to a JSON file, then run:

```bash
python3 <skill-dir>/scripts/pace_chart.py generate <race.gpx-or-kml> \
  --config <race.json> --output-dir <output-dir>
```

Set `output_formats` only for explicitly selected exports (`svg`, `html`, `csv`, `json`). Existing selected files require another directory or authorized `--overwrite`. Use the script's native renderers; they implement the table style, cutoff visibility, and metadata.

Before running, compare the configuration with the request. After success, read stdout `summary`: effective `parameters`, `target_source`, `targets_seconds`, route statistics, ordered `checkpoints`, and `verification`. Confirm finish targets/rest checks, review cutoff failures and warnings, and compare exported files with the request. For presentation-sensitive changes, render locally and inspect station names and target columns.

Deliver output paths, route statistics, targets, and material assumptions in the user's language; chart labels remain Chinese. Water values compare next-leg demand, not individual drinking needs. Do not assess fitness from a route alone.
