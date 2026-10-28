# GPX / KML Even-Effort Pace Chart Skill

[简体中文](README.md) | [English](README.en.md)

Turn a GPX or KML race route into a checkpoint-based trail-running pace chart and compare multiple finish targets. Use it as the `even-effort-pace-chart` Skill or run the command-line tool directly.

> **Source and copyright notice:** The even-effort pacing approach draws on [《耐力科学|体感一致配速表全面指南》](https://mp.weixin.qq.com/s/spYCP-upbqAZN0kzUm-0ng) by 耐力学社 / Pili（表哥）. This project independently implements equivalent-distance and fatigue curves; it is not an official RunArt.Net tool or output. Rights to the article and illustrations remain with their respective rights holders. The [repository archive](docs/reference/) preserves the original source and copyright notice; use of third-party material is subject to that notice.

- Prefer checkpoints embedded in the route; supply a manual list only when usable stations are missing.
- Expand one finish target into five schedules, 30 minutes apart by default, or specify an interval or exact target list.
- Show segment distance, ascent, descent, slope distribution, elevation thumbnails, and reference water for the next leg.
- Include station rests and supplied cutoffs; omit cutoff details from station cells when none are supplied.
- Export only SVG by default; select HTML, CSV, JSON, or additional formats through configuration.

## Quick Skill installation

With Node.js, npm, and Git installed, run this from the project where you want to use the Skill:

```bash
npx skills add yihouzenmeban/trail-running-pace --skill even-effort-pace-chart
```

Follow the prompts to select your agent. Without `-g`, installation is scoped to the current project. Add `-g` for a user-level installation available across projects:

```bash
npx skills add yihouzenmeban/trail-running-pace --skill even-effort-pace-chart -g
```

Only the selected Skill is needed; it does not depend on the repository examples or reference article at runtime. Manual copying is also supported as described below.

![Tiandi Liubai 100K pace chart](examples/tiandi-liubai-100k/pace-chart.svg)

## Requirements

Python 3.10 or newer, using only the standard library. No extra packages or online service setup are needed. Route positions must include coordinates and elevation. The XML root selects GPX or KML parsing.

## Use as a Skill

Use the installation command above, or manually copy the entire `skills/even-effort-pace-chart/` directory into your agent's skills directory, including `SKILL.md`, `agents/`, `scripts/`, and `references/`. After installation, invoke it in a conversation, replacing `race.gpx` with your own route path:

```text
$even-effort-pace-chart
Create an even-effort pace chart from race.gpx,
with a 14-hour finish target, 30-minute target intervals, and a 06:00 start. Save it to output/my-race/.
```

The Skill inspects the route and checkpoints before generating a chart. This request defaults to SVG only, with segment pace in parentheses; providing a start time does not select arrival-time display. You can also provide KML, exact target lists, station rests, and cutoffs. Chart labels currently default to Chinese.

## CLI quick start

Run these commands from the repository root. First inspect the sample route and checkpoints:

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py inspect \
  'examples/tiandi-liubai-100k/天地留白100K.gpx'
```

Generate five schedules for 12, 13, 14, 15, and 16 hours using the sample configuration:

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  'examples/tiandi-liubai-100k/天地留白100K.gpx' \
  --config examples/tiandi-liubai-100k/config.json \
  --output-dir output/tiandi-liubai-100k
```

The `output/` directory is ignored by Git. Add `--overwrite` when you intend to replace existing outputs.

The complete example in `examples/tiandi-liubai-100k/` includes the GPX, configuration, and all four exports. Its configuration explicitly selects all four `output_formats`; ordinary configurations default to SVG only. The route measures approximately 101.25 km, with 5,332 m of ascent under the current default filtering.

### KML example

LineString, gx:Track, and named Point placemarks are supported. Select among multiple routes with `track_index`. KML route positions must include heights; `altitudeMode` set to `absolute` works directly. For omitted modes or `clampToGround`, verify that the supplied heights are suitable, then add `--use-kml-altitudes` to inspection and `"use_kml_altitudes": true` to the generation configuration. This records a warning. The tool does not fill missing heights with zero, fetch terrain, or convert relative-to-ground heights into elevations. KMZ and remote NetworkLink routes are unsupported.

The Dajingmen example explicitly selects its stations and coordinate heights:

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py inspect \
  'examples/大境门/2026京东大境门古长城越野赛by UTMB®DGW100K.kml' \
  --use-kml-altitudes

python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  'examples/大境门/2026京东大境门古长城越野赛by UTMB®DGW100K.kml' \
  --config 'examples/大境门/config.json' \
  --output-dir output/dajingmen
```

`examples/大境门/` contains the original KML, configuration, and all four exports. Its altitude mode is omitted; the example explicitly uses coordinate heights and selects D1–D9, SP1, and the shared start/finish using `cp_selection`, excluding duplicate endpoints. The illustrative 24-hour target expands into five schedules from 23:00 to 25:00. The route measures approximately 99.69 km with 3,635 m of ascent, without calibration to official race statistics.

### Output files

Only `pace-chart.svg` is generated by default. Add the following field to the race configuration for additional exports; the array can also select just one format:

```json
{
  "output_formats": ["svg", "html", "csv", "json"]
}
```

| File | Purpose |
| --- | --- |
| `pace-chart.html` | Offline browser viewing and landscape printing |
| `pace-chart.svg` | Self-contained vector chart for previewing, scaling, and sharing |
| `pace-chart.csv` | Process checkpoint and target timing data in spreadsheet software |
| `pace-chart.json` | Full calculation precision, parameters, provenance, and warnings |

## Configure your race

Save the following as `race.json`:

```json
{
  "name": "我的比赛",
  "target": "14:00",
  "target_step_minutes": 30,
  "start_time": "2026-10-31 06:00"
}
```

Replace `race.gpx` with your own GPX or KML path:

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  race.gpx --config race.json --output-dir output/my-race
```

This configuration produces 13:00, 13:30, 14:00, 14:30, and 15:00 schedules. To specify exact targets, replace `target` with `targets`:

```json
{
  "targets": ["12:00", "14:00", "16:00"]
}
```

| Common parameter | Default | Meaning |
| --- | --- | --- |
| `target` / `targets` | Supply one | Central target or exact target list; use `H:MM` or `H:MM:SS`, including durations beyond 24 hours |
| `target_step_minutes` | `30` | Interval between the five schedules expanded from one target |
| `start_time` | `"06:00"` | Local race start as `HH:MM` or a full date/time; primary times remain elapsed durations |
| `secondary_display` | `"pace"` | Parenthesized value: `"pace"` for pace, `"equivalent_pace"` for equivalent pace, or `"arrival_time"` for arrival clock time |
| `output_formats` | `["svg"]` | Export format list; choose from `"svg"`, `"html"`, `"csv"`, and `"json"` |
| `pace_basis` | `"distance"` | Legacy option: `"equivalent"` selects equivalent pace; explicit `secondary_display` takes precedence |
| `sample_m` | `5` | Distance interpolation step in metres |
| `smoothing_m` | `20` | Full centered window for elevation thumbnails and slope bins, in metres |
| `ascent_smoothing_m` | `100` | Independent full window for cumulative ascent/descent, in metres |
| `use_kml_altitudes` | `false` | Explicitly use KML coordinate heights when the altitude mode is omitted or clampToGround |
| `checkpoint_overrides` | None | Set names, `rest_minutes`, `cutoff`, and other fields by candidate ID |
| `checkpoints` | Embedded stations | Manually supply names and cumulative kilometres when usable embedded CPs are unavailable |

Finish targets include station rests. Cutoffs are elapsed durations since the race start. Loops, out-and-back courses, and off-route stations may require explicit position confirmation.

A request for a 5-hour finish target, 30-minute target intervals, and a 06:00 start maps to:

```json
{
  "target": "05:00",
  "target_step_minutes": 30,
  "start_time": "06:00",
  "secondary_display": "pace",
  "output_formats": ["svg"]
}
```

When `start_time` is omitted, the race starts at 06:00 with no assumed race date; override it with `"07:30"` or a full date/time. Start time and parenthesized display are independent; set `secondary_display: "arrival_time"` only when arrival-time display is explicitly requested. Default pace uses horizontal segment distance; equivalent pace uses equivalent segment distance. Both use moving time only. Arrival clock time is before the current station's rest, with “次日” (next day) or “+N天” (+N days) for midnight rollover. All three display modes preserve the timing allocation.

See the [configuration reference](skills/even-effort-pace-chart/references/configuration.en.md) for all fields, manual CPs, and cutoff examples, and the [model reference](skills/even-effort-pace-chart/references/model.en.md) for equations and smoothing.

All optional parameters follow “current explicit request > selected configuration > script defaults.” Omit unspecified fields instead of inheriting them from examples or unrelated tasks. Valid `0` and `false` values are preserved; `null` or empty strings are not general substitutes for defaults. When reusing a configuration and replacing a target list with a central target, remove old `targets` so it does not override the new `target`. Required finish targets and ambiguous routes or stations still need explicit input.

## Development and tests

```bash
python3 -m unittest discover -s skills/even-effort-pace-chart/tests -v
```

The full repository runs synthetic GPX/KML tests and real-route regressions for Tiandi Liubai 100K and the Dajingmen KML. Real-route tests are skipped when the Skill is copied without the repository examples.

Natural-language cases in [evals/cases.json](skills/even-effort-pace-chart/evals/cases.json) cover defaults, start time independent of parenthesized display, explicit arrival display, replacing an old target list, and retaining `0/false`. Each case has Chinese and English prompts and uses the synthetic `course.gpx` in the same directory.

For each case and language, open an independent agent session, load the Skill, and provide only that language's prompt, the route, and the case's `selected_config` if present. Do not supply the expected results. Retain the configuration actually written by the agent and its execution trace, then run:

```bash
python3 skills/even-effort-pace-chart/evals/evaluate.py \
  --case start_does_not_select_arrival --config outputs/candidate.json
```

Exit code `0` means the configuration matches the case, `1` means it does not, and `2` indicates a command or file error. Manually review the trace for route inspection, no unnecessary questions about defaults, the requested exports actually being generated, and the verification summary being read. Record the model version, language, and outcome. The checker runs offline without calling an agent; it does not verify execution traces or actual files. Unit tests establish that the checker accepts correct configurations and rejects incorrect ones, not that natural-language evaluations have passed. Normal Skill use does not require loading evaluation materials.

## Model notes

Results depend on source elevations and filtering. Water values compare relative segment demand; example targets are not individual fitness assessments. The article and illustrations are background material and are not required to use the Skill.
