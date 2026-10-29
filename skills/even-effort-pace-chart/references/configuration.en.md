# Configuration and CLI

[简体中文](configuration.md) | [English](configuration.en.md)

Run with Python 3.10+; no packages, credentials, or online services are required. Paths in these examples assume the repository root. For an installed Skills package, resolve `scripts/pace_chart.py` relative to the package directory.

## Defaults and overrides

All optional parameters follow the same rule: **current explicit request > user-selected configuration > script defaults**. Build a new task's configuration from the target and explicit overrides, leaving other optional fields absent. Retain route and CP selections only when confirmed by inspection of the current route. Example targets, exports, rests, cutoffs, and track indices are example choices, not defaults to inherit.

Omitted fields use defaults. Valid `0` and `false` values take effect without being replaced; for example, `fatigue_rate: 0` disables fatigue progression and `smoothing_m: 0` disables that smoothing. `null`, empty strings, and empty lists are not general ways to request defaults; invalid types or values raise errors. `track_index: null` selects the only available track automatically, and station `cutoff: null` means no supplied cutoff.

Two compatibility precedence rules apply: a present `targets` list takes precedence over `target`, and omitted `secondary_display` honors an explicitly supplied legacy `pace_basis`. Remove the old `targets` when replacing a list with a central target. Changing one parameter does not automatically adjust other parameters. Missing finish targets, unselected multiple routes, and absent or ambiguous CPs require input rather than invented choices. If five-column expansion produces nonpositive durations, supply an explicit target list or interval instead of silently reducing the interval.

## Inspect

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py inspect race.gpx
```

Optional flags: `--track-index 1`, `--sample-m 5`, `--smoothing-m 20`, `--ascent-method hysteresis`, `--ascent-threshold-m 10`, `--ascent-smoothing-m 40`, `--elevation-spike-m 30`, and `--distance-tolerance-m 0`. The 20 m window controls graphics/slope bins. Default ascent first averages cleaned elevations over a 40 m full-width centered window (20 m on each side), then applies a 10 m peak/valley reversal threshold. Output includes horizontal distance, ascent/descent, parameters, `diagnostics`, warnings, and `cp_candidates` with IDs, names, recognition flags, and possible route projections in metres. A multiple-track error lists available track indices; repeat with the selected index.

Use the same processing parameters for inspection and generation. `diagnostics` includes original/processed distance, raw/cleaned sums of positive elevation changes, minimum/median/maximum point spacing, quality flags, spike correction counts/indices, and trial distance simplification. Final filtered ascent is the top-level `ascent_m`. Trial simplification is diagnostic, not proof of GPS drift; the horizontal path is unchanged by default.

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

`targets` takes precedence over `target`; supplying both produces a warning and sets stdout `summary.target_source` to `"targets"`. Values are sorted and must be positive and unique. An explicit list may contain one or more durations. Default five-column expansion must also produce positive durations; use an explicit list for very short races.

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

Overrides may contain `name`, `distance_km`, `rest_minutes`, `cutoff`, and `allow_off_route`. A distance override is a confirmed cumulative **processed-route kilometre** position (the original horizontal path by default), and explicitly chooses both the occurrence and location; it bypasses coordinate projection. It must lie on the route's distance interval. Recheck these positions after enabling horizontal simplification.

Stations retain their embedded names by default, with `rest_minutes` set to `0`, no cutoff check when `cutoff` is absent, and `allow_off_route` set to `false`. Without a `distance_km` override, coordinate projection and endpoint rules determine the position; manual CP names and cumulative distances are required. Do not infer rests, cutoffs, distance overrides, or off-route permission from finish targets, station names, or examples.

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

Default `distance_alignment` is `"confirm"`: differences over `max(100 m, 0.5% of route total)` stop generation. After the user confirms scaling, `"scale"` maps every official distance proportionally onto the route total. Within the tolerance, `"confirm"` preserves intermediate kilometre positions and snaps only the finish to the route endpoint. The output retains official distances and records the scale; course statistics use the processed input geometry.

## Parameters

| Key | Default | Meaning |
| --- | --- | --- |
| `target` / `targets` | Supply one | Central target or explicit target list; `targets` takes precedence |
| `name` | Input filename stem | Chart title |
| `start_time` | `"06:00"` | Local race start as `HH:MM`, `YYYY-MM-DD HH:MM`, or `YYYY-MM-DDTHH:MM`; primary times remain elapsed durations |
| `secondary_display` | `"pace"` | Parenthesized value: `"pace"` for segment pace, `"equivalent_pace"` for equivalent segment pace, or `"arrival_time"` for arrival clock time |
| `output_formats` | `["svg"]` | Non-empty list of unique export formats: `"svg"`, `"html"`, `"csv"`, and `"json"` |
| `pace_basis` | `"distance"` | Legacy option: `"equivalent"` selects equivalent pace; explicit `secondary_display` takes precedence |
| `track_index` | Only available track | 1-based GPX track/route or KML line/track selection |
| `checkpoints` | Embedded CPs | Manual list when usable embedded CPs are missing; incompatible with candidate selections or overrides |
| `cp_selection` | Recognized stations | Explicit candidate IDs from `inspect` |
| `checkpoint_overrides` | `{}` | Override selected station names, rests, cutoffs, positions, and related fields |
| `distance_alignment` | `"confirm"` | Require confirmation for a distance mismatch; only explicit `"scale"` enables proportional mapping |
| `use_kml_altitudes` | `false` | Boolean opt-in to supplied KML heights when mode is omitted or clampToGround; no effect on GPX |
| `sample_m` | 5 | Positive step in metres for display and enabled window averaging; disabling ascent averaging retains source elevation vertices |
| `smoothing_m` | 20 | Full centered averaging window for graphics and slope bins; 0 disables this smoothing |
| `ascent_method` | `"hysteresis"` | Peak/valley reversal threshold method; `"window"` selects window statistics without the reversal threshold |
| `ascent_threshold_m` | 10 | Nonnegative reversal threshold in metres; 0 disables peak/valley filtering; not a minimum adjacent-point difference |
| `ascent_smoothing_m` | 40 | Independent full centered averaging window before ascent calculation, in metres; default is 20 m on each side; 0 disables it; large windows still suppress short hills |
| `elevation_spike_m` | 30 | Minimum residual in metres for isolated elevation spikes; 0 disables correction; distance/grade conditions also apply |
| `distance_tolerance_m` | 0 | Horizontal simplification tolerance in metres; 0 disables it; positive values can shorten real small turns |
| `ascent_km_per_100m` | 1 | Equivalent kilometres per 100 m ascent; nonnegative |
| `fatigue_rate` | 0.08 | Pace multiplier minus one per doubling; range 0 to 1 |
| `water_ml_per_10km` | 700 | Comparative water per 10 equivalent km; nonnegative |
| `target_step_minutes` | 30 | Positive interval for five-column expansion |

Unknown configuration and station fields are errors. Numbers must be finite. No measured elevation is fetched or invented; fix missing elevations in the source before generation. Sampling allows at most 2,000,000 intervals plus the exact endpoint; excessively small `sample_m` values return an input error. Positive smoothing windows too small to compute their boundaries reliably also return an error; increase the corresponding window or set it to `0` to disable smoothing.

See the [model and limitations](model.en.md) for elevation filtering and timing equations.

### Previous window method and explicit filtering

To select the previous 100 m window approach, add to an existing target configuration:

```json
{
  "ascent_method": "window",
  "ascent_smoothing_m": 100
}
```

Inspect with `--ascent-method window --ascent-smoothing-m 100`. Boundary and integration fixes also apply, so results need not exactly match older versions. An old configuration specifying only `ascent_smoothing_m: 100` now applies the default reversal threshold after that window; explicitly choose `window` for window statistics alone.

Horizontal simplification requires an explicit value such as `"distance_tolerance_m": 2`; inspect with `--distance-tolerance-m 2`. Do not enable it automatically because trial distance decreases. Elevation spike correction is enabled by default and reported; use `"elevation_spike_m": 0` when all source elevations must be retained. Also set `ascent_threshold_m` and `ascent_smoothing_m` to 0 to sum elevation changes directly at source vertices. Input files are never rewritten.

## Parenthesized display

`secondary_display` controls the parenthesized value and heading label in both HTML and SVG:

`start_time` and the parenthesized display are independent. Providing only a 06:00 start still defaults to pace in parentheses; select `"arrival_time"` only when the user explicitly requests it or supplies a configuration selecting it.

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

Only `pace-chart.svg` is written by default. Set `output_formats` in the race configuration for other exports. This example selects all four formats; you can select one or several instead. Returned paths follow the array order:

```json
{
  "output_formats": ["svg", "html", "csv", "json"]
}
```

Empty lists, unsupported formats, and duplicate formats are errors. Use `--overwrite` only when replacement is intended. Otherwise any existing file for a **selected format** blocks writing; existing unselected files do not block generation and are neither modified nor deleted. Output targets cannot be directories or symlinks. All selected content is staged in a temporary directory inside the output directory, with existing files backed up, before replacement begins. A replacement file error restores replaced files and removes newly created outputs. If recovery itself fails, the temporary directory is retained and reported in `details.recovery_directory` for manual recovery. This handles catchable file errors; it does not guarantee multi-file atomicity across power loss, forced process termination, or concurrent writes. Avoid concurrent generation into the same output directory.

Successful stdout is JSON with these fields, without requiring a JSON file export:

| Field | Content |
| --- | --- |
| `outputs` | Files generated in this run, in `output_formats` order |
| `warnings` | Model limitations, missing cutoffs, configuration conflicts, and other warnings |
| `summary.parameters` | Effective numeric parameters, output formats, parenthesized display, start time, and total rest seconds |
| `summary.target_source` / `summary.targets_seconds` | Whether `target` or `targets` supplied the effective targets, and their sorted seconds |
| `summary.route` / `summary.checkpoints` | Route statistics with input-quality and before/after `diagnostics`, plus ordered CP IDs, names, cumulative metres, rest seconds, and cutoff seconds |
| `summary.verification` | `finish_targets_match` checks finish times against targets; `rests_match` checks departure minus arrival against station rest; `cutoff_checked_stations` / `cutoff_unchecked_stations` count stations excluding the start; `cutoff_failures` lists target seconds, CP IDs, and late statuses |

The summary omits full profiles and complete schedules; explicitly export JSON for those. Verification checks calculation consistency, not event rules. Expected input/file errors print a JSON object to stderr and exit with status 2.

Available exports are listed below. Only SVG is generated by default; other files require explicit selection:

- `pace-chart.html`: reference-style race table with white background, gray rules, black graphics, yellow/red/green/blue terrain/supply columns, repeated print headers, and horizontal scrolling on small screens.
- `pace-chart.svg`: native SVG table with text and vector segment graphics; no HTML `foreignObject` or external assets.
- `pace-chart.csv`: UTF-8 BOM, long form with one row per CP and target. Includes raw seconds and formatted cumulative durations, incoming `segment_water_ml`, and next-leg `water_ml`. Potential formula-leading CP names are escaped for spreadsheets.
- `pace-chart.json`: full-precision source of truth with parameters, configuration, input SHA-256, station statistics, schedule values, slope fractions, profiles, warnings, and article attribution. Schema version 2; geometry in metres, times in seconds, equivalent distances in kilometres. In version 2, `water_ml` describes the outgoing leg; `segment_water_ml` describes the incoming leg.

Primary cumulative times are departures, shown as `HH:MM` by truncating seconds, including durations over 24 hours. In pace modes, resting CPs also show elapsed arrival on an extra line. Arrival clock mode puts arrival in parentheses and omits that extra line. JSON/CSV include `distance_pace_seconds_per_km`, `eq_pace_seconds_per_km`, and the selected `pace_seconds_per_km`; arrival and departure remain elapsed seconds since the start, with clock times used only for chart presentation. HTML/SVG headers use `Target` and hours. CSV formatted arrival/departure retain seconds, and raw JSON/CSV values retain calculation precision. Station cells display cutoff information only when supplied; missing cutoffs remain in CLI warnings and JSON. Actual cutoff violations appear in their target cells. JSON/CSV include the status of every CP.

Visible HTML/SVG content ends with the table, without explanatory footer text. Calculation parameters and warnings remain in JSON and CLI output. Source attribution is retained in HTML/SVG metadata and JSON.

The water column is a station supply reference for the **next** leg: the start contains the first leg's value, each intermediate station contains the following leg's value, and the finish contains 0. Terrain statistics and parenthesized pace describe the leg just completed. Segment equivalent distance remains in CSV/JSON rather than consuming an extra visual column.

The legacy CSV column `gpx_distance_km` contains cumulative horizontal distance from the selected input geometry for **both GPX and KML**. The distance-mismatch error's legacy `gpx_m` field likewise refers to the input route total in metres. These names are retained for compatibility. Chart labels remain Chinese; bilingual documentation does not change output labels.
