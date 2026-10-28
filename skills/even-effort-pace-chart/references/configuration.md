# Configuration and CLI

Run with Python 3.10+; no packages, credentials, or online services are required. Paths in these examples assume the repository root. For an installed skill, resolve `scripts/pace_chart.py` relative to its skill folder.

## Inspect

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py inspect race.gpx
```

Optional flags: `--track-index 1`, `--sample-m 5`, `--smoothing-m 20`. Output includes horizontal distance, smoothed ascent/descent, warnings, and `cp_candidates` with stable IDs, names, recognition flags, and possible route projections in metres. A multiple-track error lists available track indices; repeat with the selected index.

Tracks take precedence over routes for course geometry. Separate route points and waypoints can still supply CPs. When only routes exist, the chosen route supplies both geometry and named CP candidates. GPX 1.0, 1.1, and unnamespaced files are accepted. Every track point needs valid coordinates and elevation. Duplicated positions are removed; disconnected track segments are rejected rather than connected by a fabricated line.

## Target-only configuration

If the GPX already contains usable CPs:

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

Overrides may contain `name`, `distance_km`, `rest_minutes`, `cutoff`, and `allow_off_route`. A distance override is a confirmed cumulative **GPX kilometre** position, and explicitly chooses both the occurrence and location; it bypasses coordinate projection. It must lie on the route's distance interval.

A recognized shared start/finish waypoint within 100 m of both endpoints becomes `<candidate-id>:start` and `<candidate-id>:finish`, with the venue name preserved. Configure it using the original candidate ID. Its cutoff applies to the finish only, and rest must be zero. A `distance_km` override treats it as one explicitly positioned station instead.

Cutoffs are elapsed durations since the race start. Arrival after cutoff yields `arrival_late`; arrival on time followed by departure after cutoff yields `departure_late`. This flags both interpretations without assuming the organizer's rule. Times exactly equal to the cutoff are on time. An absent cutoff is `not_checked`. Start and finish cannot have departure rests.

## Manual CP list

Use only when GPX CPs are absent or unsuitable. Include a final finish with a cumulative official distance. A zero-distance start is optional.

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

Default `distance_alignment` is `"confirm"`: differences over `max(100 m, 0.5% of GPX total)` stop generation. After the user confirms scaling, `"scale"` maps every official distance proportionally onto the GPX total. Within the tolerance, `"confirm"` preserves intermediate kilometre positions and snaps only the finish to the GPX endpoint. The output retains official distances and records the scale; course statistics always use GPX geometry.

## Parameters

| Key | Default | Meaning |
| --- | --- | --- |
| `name` | GPX filename stem | Chart title |
| `track_index` | Only available track | 1-based track or route selection |
| `sample_m` | 5 | Positive distance resampling step in metres |
| `smoothing_m` | 20 | Full centered averaging window in metres; 0 disables smoothing |
| `ascent_km_per_100m` | 1 | Equivalent kilometres per 100 m ascent; nonnegative |
| `fatigue_rate` | 0.08 | Pace multiplier minus one per doubling; range 0 to 1 |
| `water_ml_per_10km` | 700 | Comparative water per 10 equivalent km; nonnegative |
| `target_step_minutes` | 30 | Positive interval for five-column expansion |

Unknown configuration and station fields are errors. Numbers must be finite. No measured elevation is fetched or invented; fix missing elevations in the source before generation. Sampling is limited to 2,000,000 points to prevent accidental excessive allocation.

## Generate and outputs

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate race.gpx \
  --config race.json --output-dir output/race
```

Use `--overwrite` only when replacing those output files is intended. Otherwise any existing output blocks writing. Success prints output paths and warnings to stdout. Expected input/file errors print a JSON object to stderr and exit with status 2.

- `pace-chart.html`: printable landscape table, repeated headers, inline segment graphics, horizontal scrolling on small screens.
- `pace-chart.svg`: native SVG table with text and vector segment graphics; no HTML `foreignObject` or external assets.
- `pace-chart.csv`: UTF-8 BOM, long form with one row per CP and target. Includes raw seconds and formatted cumulative durations. Potential formula-leading CP names are escaped for spreadsheets.
- `pace-chart.json`: full-precision source of truth with parameters, configuration, input SHA-256, station statistics, schedule values, slope fractions, profiles, warnings, and article attribution. Schema version 1; geometry in metres, times in seconds, equivalent distances in kilometres.

Primary cumulative times are departures. Resting CPs also show arrival. Parentheses contain the segment's moving-time equivalent pace, not actual min/km over horizontal distance. Missing cutoffs are listed in the warnings; actual cutoff violations appear in their target cells. JSON/CSV include the status of every CP.
