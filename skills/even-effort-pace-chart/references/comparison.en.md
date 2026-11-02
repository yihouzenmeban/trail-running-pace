# Recorded activity versus pace plans

[简体中文](comparison.md) | [English](comparison.en.md)

Use `../scripts/compare_activity.py`. It reuses the route processing, checkpoint selection, distance, ascent, and pacing model in `pace_chart.py`. GPX/KML and embedded/manual checkpoints are supported without changing the race configuration. Comparisons require an optional dependency; ordinary pace charts remain standard-library-only:

```bash
python3 -m pip install -r <skill-dir>/scripts/requirements-comparison.txt
```

## Offline inspection and generation

Provide a race route, pace configuration, and a single-activity original FIT or ZIP containing exactly one FIT. Optionally supply Garmin activity-details JSON. Without it, totals come from the FIT session and are labeled accordingly. `--targets` supplies an exact list, overriding configured `target`/`targets` without five-column expansion or modifying the source configuration. Without this flag, configured targets and existing defaults apply.

```bash
python3 <skill-dir>/scripts/compare_activity.py inspect race.gpx \
  --config race.json --fit activity-original.zip --summary activity-details.json \
  --targets 15:00 16:00 17:00

python3 <skill-dir>/scripts/compare_activity.py generate race.gpx \
  --config race.json --fit activity-original.zip --summary activity-details.json \
  --targets 15:00 16:00 17:00 --output-dir output/comparison
```

`inspect` prints activity totals, matched checkpoints, segment times, terrain estimates, and warnings without writing files. `generate` writes only `garmin-comparison.svg` by default. The header collects actual finish time and the final advantage or deficit against each target. The body has two sections:

1. **Time performance:** one panel per target, up to three per row, with a cumulative difference curve above and positive/negative segment difference bars below. A shared readout follows, with checkpoint columns and one row for Garmin actual times and each target plan. Each cell shows cumulative / segment `HH:MM:SS` values on one line. Cumulative time runs from the start to that checkpoint; segment time runs from the previous checkpoint. Headers show station names and cumulative course distance. Many checkpoints wrap into blocks, each repeating the source rows.
2. **Course data comparison:** total distance, ascent, and descent cards followed directly by grouped segment ascent/descent bars. Both values are paired by checkpoint interval and share a scale starting at zero. Checkpoint header tooltips retain both cumulative distances; terrain tooltips retain segment elevation differences.

For time, green means actually ahead/faster, red means behind/slower, and gray means a tie, with explicit text labels. Cumulative curves align checkpoints by route distance and share a scale across targets: above zero means ahead, below means behind, with color changes at zero crossings. Segment bars use equal-width checkpoint intervals and another shared symmetric scale: above zero means faster, below means slower. Labels show minutes, except non-ties below six seconds, which show seconds. The readout uses neutral colors with bold actual times and no repeated difference color blocks. Terrain uses dark gray for Garmin and blue for the repository without a judgment of better/worse. Unknown values show `—` without a corresponding bar.

When opened directly in a browser, curve points, segment bars, time cells, checkpoint headers, and terrain groups support hover or Tab focus for times and values. Terrain tooltips explicitly state repository-more/less differences. Static images directly show actual and planned cumulative times, segment times, faster/slower differences, and both segment ascent/descent values. Footnotes retain essential definitions, with full provenance and warnings in tooltips and SVG metadata. Curves and bars take design cues from ECharts; Python still generates the SVG directly, without extra HTML or an external chart library.

Time labels describe the **recorded activity**: `plan minus Garmin > 0` means actually ahead/faster; `< 0` means behind/slower. Absolute differences below half a second display as a tie. Terrain differences mean **repository minus Garmin**, computed before rounding to meters. Readout and tooltip times include seconds and support durations beyond 24 hours. Add `--export-json` for unrounded `garmin-comparison.json`, which retains the original plan-minus-actual deltas. It excludes raw GPS records but includes activity identity, passage times, and estimated metrics. Existing files require another output directory or authorized `--overwrite`.

## Passage matching and timing semantics

Embedded checkpoints use their original coordinates. Manual checkpoints and checkpoints with explicit `distance_km` overrides use the corresponding processed-route position. Projection uses geometric distance to locate the passage, then interpolates recorded activity distance and elapsed time; geometric distance is not substituted for Garmin distance.

Repeated passages, offsets over 100 m, substantial checkpoint standstills, or nonmonotonic station order produce actionable diagnostics instead of silently selecting the nearest occurrence. Different projections near a station stop can also differ by seconds; automatic matching is not official timing.

After confirming the passage, supply overrides as JSON. Keys must be checkpoint IDs from inspection/diagnostics, not guessed names or indices. Values accept `H:MM[:SS]` or elapsed seconds with fractional precision:

```json
{
  "wpt:3": "03:08:35",
  "manual:2": 16638.987685
}
```

```bash
python3 <skill-dir>/scripts/compare_activity.py generate race.gpx \
  --config race.json --fit activity.fit --targets 15:00 16:00 17:00 \
  --passage-overrides passages.json --output-dir output/comparison
```

Only intermediate checkpoints accept overrides. Times must fall within GPS coverage and preserve passage order. Endpoints use activity start/finish and must be within 100 m of route endpoints; otherwise select the appropriate activity or route. Overrides, offsets, and input hashes are recorded in chart metadata. Numeric seconds preserve the precision of previously reviewed passages.

Actual segment time is `current passage elapsed − previous passage elapsed`. Planned segment time is `current planned arrival − previous planned arrival`, including configured rest at the previous station. Both include stops between matched passages. Neither isolates moving-only time or station dwell. Subtract unrounded values before display rounding. Unrounded segments sum to the total; displayed values may differ by a few seconds.

## Terrain and input limitations

Intermediate Garmin cumulative ascent/descent is estimated by linear interpolation over FIT lap distances. Adjacent cumulative estimates are subtracted for segment values; the climb's actual position inside a lap is unknown. Missing lap distance disables intermediate terrain estimates. Missing ascent/descent makes subsequent corresponding cumulative values unknown. Unknown values display `—`; they are never zero-filled or replaced by a new elevation calculation.

With platform details, supplied platform total fields take precedence, with FIT session fallback for other fields. Without details, use session totals. Lap and platform totals can differ: report differences without rescaling; reject decreasing cumulative terrain. Records missing GPS/time/distance are skipped and reported; long interpolation gaps produce warnings. Damaged FIT, multiple sessions, and decreasing record distance/time are errors.

## Garmin network commands

Use `list`/`fetch` when the user requests activity retrieval. Credentials come from `GARMIN_PERSONAL_API_KEY` or explicit `--env-file .env.local`; the environment takes precedence. Env files accept literal values without shell execution or variable expansion. Never put credentials in code, configuration, or command-line arguments. Keep raw personal activities in Git-ignored `output/`, outside public tracked examples.

```bash
python3 <skill-dir>/scripts/compare_activity.py list \
  --start-date 2026-10-01 --end-date 2026-11-02 --limit 20 --env-file .env.local

python3 <skill-dir>/scripts/compare_activity.py fetch <activity-id> --env-file .env.local
```

`list` returns activities with pagination via `--start`/`--limit`. `fetch` saves `activity-details.json` and `activity-original.zip` under `output/activities/<activity-id>/` by default. Select another directory with `--output-dir`; existing caches require `--overwrite`. File permissions are `600`; bearer tokens stay in memory.

The default region is `--region com`; select `--region cn` explicitly for China. No automatic regional fallback or retries occur. `--timeout` defaults to 45 seconds. Authentication/network errors report status without response bodies, keys, or tokens.
