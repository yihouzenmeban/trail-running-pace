# Dajingmen DGW100K: 15-hour pace plan

[简体中文](README.md) | [English](README.en.md) | [DGW100K example](../README.en.md)

Five finish targets are centered on 15 hours: 14:00, 14:30, 15:00, 15:30, and 16:00. Segment pace appears in parentheses. Elapsed time starts at the gun; the default configuration includes no station rests or cutoff checks.

- [pace-chart.html](pace-chart.html): a chart for viewing and printing.
- [pace-chart.svg](pace-chart.svg): a standalone chart.
- [config.json](config.json): targets, station selection, and export formats.

The default distance mode compares water demand at 700 ml per 10 equivalent kilometres; it is not a personal drinking recommendation. Distance comes from the KML route and is not scaled to station names. Elevations use the KML coordinates without terrain or vertical-datum correction. The displayed 06:00 start is a tool default, not a confirmed race time. Check station water supplies, carrying capacity, and personal needs before planning water.

Run from the repository root:

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  'examples/大境门/DGW100K/2026京东大境门古长城越野赛by UTMB®DGW100K.kml' \
  --config 'examples/大境门/DGW100K/15h/config.json' \
  --output-dir output/dgw100k-15h
```

Results are written to Git-ignored `output/dgw100k-15h/`; add `--overwrite` only when replacing existing results.
