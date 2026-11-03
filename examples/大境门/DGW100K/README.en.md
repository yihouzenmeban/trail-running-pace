# Dajingmen DGW100K example

[简体中文](README.md) | [English](README.en.md) | [Project home](../../../README.en.md)

This example uses a user-supplied race KML copy. Both the route and configuration are public, allowing the pace chart to be regenerated.

## Inputs and results

| File | Contents |
| --- | --- |
| [Race KML](2026京东大境门古长城越野赛by%20UTMB®DGW100K.kml) | Original route and checkpoint candidates |
| [config.json](config.json) | 15 plans from 10h to 24h, one hour apart; 06:00 start; explicitly selected CPs and KML coordinate heights |
| [pace-chart.svg](pace-chart.svg) | Segment pace in parentheses; the same configuration also exports HTML, CSV, and JSON |

`cp_selection` explicitly selects candidates from this file; these IDs are not defaults for other routes. Inspect candidates again if the KML is re-exported.

## Reproduction

Requires Python 3.10+. Run from the repository root:

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py inspect \
  'examples/大境门/DGW100K/2026京东大境门古长城越野赛by UTMB®DGW100K.kml' \
  --use-kml-altitudes

python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  'examples/大境门/DGW100K/2026京东大境门古长城越野赛by UTMB®DGW100K.kml' \
  --config 'examples/大境门/DGW100K/config.json' \
  --output-dir output/dgw100k
```

This example explicitly uses the supplied coordinate heights: inspection passes `--use-kml-altitudes`, and generation sets `use_kml_altitudes: true`. That choice does not establish surveyed heights. Verify the meaning of heights in other KML files before using the switch. See [KML input](../../../skills/even-effort-pace-chart/references/configuration.en.md#kml-input) for the full rules.

All four formats go into Git-ignored `output/dgw100k/`; add `--overwrite` to replace existing results. This directory has no recorded-activity comparison. Historical ascent-method figures are in [ascent methods](../../../skills/even-effort-pace-chart/references/ascent-options.en.md). Reproduction means recomputing plans from the same inputs, not byte-identical output across code versions.
