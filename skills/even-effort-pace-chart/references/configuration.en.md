# Configuration and CLI

[简体中文](configuration.md) | [English](configuration.en.md)

Run with Python 3.10+; no packages, credentials, or online services are required. Paths in these examples assume the repository root. For an installed skill, resolve `scripts/pace_chart.py` relative to its skill folder.

## Inspect

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py inspect race.gpx
```

Optional flags: `--track-index 1`, `--sample-m 5`, `--smoothing-m 20`, `--ascent-smoothing-m 100`. The 20 m window controls detailed graphics/slope bins; the independent 100 m window controls ascent/descent statistics. Output includes horizontal distance, filtered ascent/descent, parameters, warnings, and `cp_candidates` with stable IDs, names, recognition flags, and possible route projections in metres. A multiple-track error lists available track indices; repeat with the selected index.

Tracks take precedence over routes for course geometry. Separate route points and waypoints can still supply CPs. When only routes exist, the chosen route supplies both geometry and named CP candidates. GPX 1.0, 1.1, and unnamespaced files are accepted. Every track point needs valid coordinates and elevation. Duplicated positions are removed; disconnected track segments are rejected rather than connected by a fabricated line.

## KML input

The XML root selects GPX or KML parsing; the filename extension does not select the parser. Local KML supports LineString and gx:Track, including Document/Folder, MultiGeometry, and gx:MultiTrack containers. A geometry inherits its container's altitude mode unless it declares its own. Each line or track is an independent `track_index` selection in document order; separate lines are never joined automatically. KML coordinates are `longitude,latitude,altitude`; gx:coord uses space-separated `longitude latitude altitude`. Original gx:Track timestamps are not used to allocate race targets.

Every route position needs a finite altitude. An explicit `altitudeMode: absolute` is accepted directly. An omitted mode defaults to ground clamping in KML; coordinate heights cannot automatically be treated as elevations. If you have verified those heights, opt in with `--use-kml-altitudes` for inspection and `"use_kml_altitudes": true` for generation. Explicit clampToGround also requires this opt-in. The choice produces a warning and remains in the output configuration. Missing heights are never filled with zero. Relative-to-ground and sea-floor modes are rejected even with the override; re-export absolute elevations. No terrain is downloaded or datum correction performed.

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py inspect race.kml --use-kml-altitudes
```

```json
{
  "target": "24:00",
  "use_kml_altitudes": true
}
```

Named KML Point placemarks supply CP candidates; point elevations are optional. IDs such as `placemark:3:point:1` identify the third Placemark in document order and its first Point geometry. Use the IDs returned by `inspect`; editing the source may change them. Names such as D1 or arbitrary villages require explicit `cp_selection`. If a file contains both separate start/finish points and a shared start/finish point, select one representation to avoid duplicate endpoints. KMZ, polygons as routes, and remote NetworkLink fetching are unsupported. GPX and KML inputs use the same configuration and four exporters.

## Target-only configuration

If the input route already contains usable CPs:

```json
{
  "name": "Example trail race",
  "target": "24:00"
}
```

This produces 23:00, 23:30, 24:00, 24:30, and 25:00. These are finish durations, not times of day. `H:MM` and `H:MM:SS` are accepted; durations can exceed 24 hours.

For a different five-column interval, use `"target_step_minutes": 15`. For an exact list, use:

```json
{
  "targets": ["22:30", "24:00", "27:15"]
}
```

`targets` takes precedence over `target`; values are sorted and must be positive and unique. An explicit list may contain one or more durations. Default five-column expansion must also produce positive durations; use an explicit list for very short races.

## CP selection and overrides

The IDs below are illustrative; use the actual IDs returned by `inspect`.

```json
{
  "target": "24:00",
  "cp_selection": ["wpt:1", "wpt:2", "wpt:3"],
  "checkpoint_overrides": {
    "wpt:1": {"name": "CP1 - Village", "rest_minutes": 5, "cutoff": "04:30"},
    "wpt:2": {"distance_km": 37.25},
    "wpt:3": {"allow_off_route": true}
  }
}
```

Without `cp_selection`, recognized CP/SP, checkpoint, aid station, water station, start/finish, and corresponding Chinese names/types are selected. Selection order is normalized to cumulative route distance. Arbitrarily named waypoints require explicit IDs; ordinary landmarks are not promoted automatically. Ambiguous route occurrences and offsets over 100 m stop generation with actionable JSON errors.

Overrides may contain `name`, `distance_km`, `rest_minutes`, `cutoff`, and `allow_off_route`. A distance override is a confirmed cumulative **input-route kilometre** position, and explicitly chooses both the occurrence and location; it bypasses coordinate projection. It must lie on the route's distance interval.

A recognized shared start/finish waypoint within 100 m of both endpoints becomes `<candidate-id>:start` and `<candidate-id>:finish`, with the venue name preserved. Configure it using the original candidate ID. Its cutoff applies to the finish only, and rest must be zero. A `distance_km` override treats it as one explicitly positioned station instead.

Cutoffs are elapsed durations since the race start. Arrival after cutoff yields `arrival_late`; arrival on time followed by departure after cutoff yields `departure_late`. This flags both interpretations without assuming the organizer's rule. Times exactly equal to the cutoff are on time. An absent cutoff is `not_checked`. Start and finish cannot have departure rests.

## Manual CP list

Use only when embedded CPs are absent or unsuitable. Include a final finish with a cumulative official distance. A zero-distance start is optional.

```json
{
  "target": "24:00",
  "distance_alignment": "scale",
  "checkpoints": [
    {"name": "Start", "distance_km": 0},
    {"name": "CP1", "distance_km": 25, "rest_minutes": 8, "cutoff": "06:00"},
    {"name": "CP2", "distance_km": 60, "rest_minutes": 12, "cutoff": "15:00"},
    {"name": "Finish", "distance_km": 100, "cutoff": "28:00"}
  ]
}
```

Distances must increase strictly. `checkpoints` cannot be mixed with GPX selections or overrides. Start/finish rests must be zero.

Default `distance_alignment` is `"confirm"`: differences over `max(100 m, 0.5% of route total)` stop generation. After the user confirms scaling, `"scale"` maps every official distance proportionally onto the route total. Within the tolerance, `"confirm"` preserves intermediate kilometre positions and snaps only the finish to the route endpoint. The output retains official distances and records the scale; course statistics always use input-route geometry.

## Parameters

| Key | Default | Meaning |
| --- | --- | --- |
| `name` | Input filename stem | Chart title |
| `start_time` | `"06:00"` | Local race start as `HH:MM`, `YYYY-MM-DD HH:MM`, or `YYYY-MM-DDTHH:MM`; primary times remain elapsed durations |
| `secondary_display` | `"pace"` | Parenthesized value: `"pace"` for segment pace, `"equivalent_pace"` for equivalent segment pace, or `"arrival_time"` for arrival clock time |
| `pace_basis` | `"distance"` | Legacy option: `"equivalent"` selects equivalent pace; explicit `secondary_display` takes precedence |
| `track_index` | Only available track | 1-based GPX track/route or KML line/track selection |
| `use_kml_altitudes` | `false` | Boolean opt-in to supplied KML heights when mode is omitted or clampToGround; no effect on GPX |
| `sample_m` | 5 | Positive distance resampling step in metres |
| `smoothing_m` | 20 | Full centered averaging window for graphics and slope bins; 0 disables this smoothing |
| `ascent_smoothing_m` | 100 | Independent full centered window for cumulative ascent/descent on the same fine grid; 0 disables this filtering |
| `ascent_km_per_100m` | 1 | Equivalent kilometres per 100 m ascent; nonnegative |
| `fatigue_rate` | 0.08 | Pace multiplier minus one per doubling; range 0 to 1 |
| `water_ml_per_10km` | 700 | Comparative water per 10 equivalent km; nonnegative |
| `target_step_minutes` | 30 | Positive interval for five-column expansion |

Unknown configuration and station fields are errors. Numbers must be finite. No measured elevation is fetched or invented; fix missing elevations in the source before generation. Sampling is limited to 2,000,000 points to prevent accidental excessive allocation.

See the [model and limitations](model.en.md) for elevation filtering and timing equations.

## Parenthesized display

`secondary_display` controls the parenthesized value and heading label in both HTML and SVG:

| Value | Chinese label | Calculation |
| --- | --- | --- |
| `"pace"` | 区间配速 | Segment moving seconds / horizontal segment kilometres; default |
| `"equivalent_pace"` | 区间等强配速 | Segment moving seconds / equivalent segment kilometres |
| `"arrival_time"` | 到达时间 | `start_time` + cumulative arrival duration, before this station's rest |

Both pace modes show `MM:SS` rounded to seconds. The start has no incoming leg and therefore no parenthesized pace. Arrival clock mode shows `HH:MM` truncated to minutes, including the gun time at the start. After midnight relative to the start day, it labels the next day “次日” and later days “+N天”, for example `(次日 01:20)` and `(+2天 00:30)`. Times use local race time without time-zone or daylight-saving conversion. Omitted `start_time` defaults to 06:00 without assuming a race date; an explicit time takes precedence. JSON `parameters.start_time` records the effective value.

For example, add these fields to a configuration that includes a finish target:

```json
{
  "start_time": "2026-10-31 23:30",
  "secondary_display": "arrival_time"
}
```

When `secondary_display` is absent, legacy `pace_basis: "equivalent"` still selects equivalent pace; otherwise pace is the default. Explicit `"pace"` or `"equivalent_pace"` also sets the output `pace_basis` parameter and JSON/CSV `pace_seconds_per_km` to the selected basis. `"arrival_time"` keeps the original `pace_basis` for numeric pace fields. Both raw pace fields remain available, and all three modes preserve the timing allocation.

## Generate and outputs

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate race.gpx \
  --config race.json --output-dir output/race
```

Use `--overwrite` only when replacing those output files is intended. Otherwise any existing output blocks writing. Success prints output paths and warnings to stdout. Expected input/file errors print a JSON object to stderr and exit with status 2.

- `pace-chart.html`: reference-style race table with white background, gray rules, black graphics, yellow/red/green/blue terrain/supply columns, repeated print headers, and horizontal scrolling on small screens.
- `pace-chart.svg`: native SVG table with text and vector segment graphics; no HTML `foreignObject` or external assets.
- `pace-chart.csv`: UTF-8 BOM, long form with one row per CP and target. Includes raw seconds and formatted cumulative durations, incoming `segment_water_ml`, and next-leg `water_ml`. Potential formula-leading CP names are escaped for spreadsheets.
- `pace-chart.json`: full-precision source of truth with parameters, configuration, input SHA-256, station statistics, schedule values, slope fractions, profiles, warnings, and article attribution. Schema version 2; geometry in metres, times in seconds, equivalent distances in kilometres. In version 2, `water_ml` describes the outgoing leg; `segment_water_ml` describes the incoming leg.

Primary cumulative times are departures, shown as `HH:MM` by truncating seconds, including durations over 24 hours. In pace modes, resting CPs also show elapsed arrival on an extra line. Arrival clock mode puts arrival in parentheses and omits that extra line. JSON/CSV include `distance_pace_seconds_per_km`, `eq_pace_seconds_per_km`, and the selected `pace_seconds_per_km`; arrival and departure remain elapsed seconds since the start, with clock times used only for chart presentation. HTML/SVG headers use `Target` and hours. CSV formatted arrival/departure retain seconds, and raw JSON/CSV values retain calculation precision. Station cells display cutoff information only when supplied; missing cutoffs remain in CLI warnings and JSON. Actual cutoff violations appear in their target cells. JSON/CSV include the status of every CP.

Visible HTML/SVG content ends with the table, without explanatory footer text. Calculation parameters and warnings remain in JSON and CLI output. Source attribution is retained in HTML/SVG metadata and JSON.

The water column is a station supply reference for the **next** leg: the start contains the first leg's value, each intermediate station contains the following leg's value, and the finish contains 0. Terrain statistics and parenthesized pace describe the leg just completed. Segment equivalent distance remains in CSV/JSON rather than consuming an extra visual column.

The legacy CSV column `gpx_distance_km` contains cumulative horizontal distance from the selected input geometry for **both GPX and KML**. The distance-mismatch error's legacy `gpx_m` field likewise refers to the input route total in metres. These names are retained for compatibility. Chart labels remain Chinese; bilingual documentation does not change output labels.
