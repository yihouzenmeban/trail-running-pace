# Dajingmen MGW50K example

[简体中文](README.md) | [English](README.en.md) | [Project home](../../../README.en.md)

The directory retains the name `DGW50K`, while route and chart titles use the race category `MGW50K`. Public files reproduce two pace charts. The merged three-source comparison is a manually assembled historical reference.

## Inputs and elevation repair

The [original GPX](2026京东大境门古长城越野赛by%20UTMB®MGW50K.gpx) lacks elevation at 59 points; use the filled copy below to generate charts. The two gaps span approximately 834.6 m and 34.1 m between known endpoints.

[MGW50K-elevation-filled.gpx](MGW50K-elevation-filled.gpx) is a copy with elevations linearly interpolated along horizontal distance between known endpoints. [elevation-repair.json](elevation-repair.json) records point indices, gaps, the repair method, and hashes of both files. The copy is ready to use; interpolation cannot recover missing hills.

## Pace charts and reproduction

| Configuration | Plans | Result |
| --- | --- | --- |
| [config.json](config.json) | 16 plans from 5h to 12.5h, 30 minutes apart | [pace-chart.svg](pace-chart.svg) |
| [config-6h15m.json](config-6h15m.json) | A single 6h15m plan | [pace-chart-6h15m.svg](pace-chart-6h15m.svg) |

Both configurations use the defaults: SVG, a 06:00 start, and segment pace in parentheses. Both explicitly select CP IDs from this route.

![Dajingmen MGW50K: a single 6-hour 15-minute pace plan](pace-chart-6h15m.svg)

Requires Python 3.10+. Run from the repository root:

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py inspect \
  'examples/大境门/DGW50K/MGW50K-elevation-filled.gpx'

python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  'examples/大境门/DGW50K/MGW50K-elevation-filled.gpx' \
  --config 'examples/大境门/DGW50K/config.json' \
  --output-dir output/dgw50k

python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  'examples/大境门/DGW50K/MGW50K-elevation-filled.gpx' \
  --config 'examples/大境门/DGW50K/config-6h15m.json' \
  --output-dir output/dgw50k-6h15m
```

Results go into Git-ignored `output/`; add `--overwrite` to replace existing files.

## Historical three-source comparison

[runart-comparison.svg](runart-comparison.svg) combines data transcribed from a 耐力学社 / RunArt.Net pace-chart screenshot, repository plans, and the Garmin Dajingmen activity from September 12, 2026. It presents:

1. Cumulative checkpoint times across all 16 targets.
2. Cumulative distance and segment ascent/descent for all three sources, with RunArt-minus-Garmin and repository-minus-Garmin differences beside their values.
3. Repository 6:15 plans against actual Garmin checkpoint times; time differences mean actual minus plan, so negative means earlier.

![Dajingmen MGW50K: historical comparison of RunArt, repository plans, and the Garmin activity](runart-comparison.svg)

Elapsed times include stops. Intermediate terrain values are estimated by distance interpolation within FIT laps, then differenced between adjacent cumulative values. Finish totals come from the platform; differences are computed before rounding. The raw personal FIT is not published.

The three-source chart is provided as an SVG. To generate a plan-versus-activity comparison from your own FIT, see the [activity comparison reference](../../../skills/even-effort-pace-chart/references/comparison.en.md).
