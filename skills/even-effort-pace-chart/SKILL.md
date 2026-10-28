---
name: even-effort-pace-chart
description: Convert a GPX race route into an even-effort trail running pace chart with checkpoint splits, elevation profiles, and multiple finish targets. Use when planning race pacing from GPX or generating HTML, SVG, CSV, and JSON pace tables.
---

# Even-Effort Pace Chart

Use `scripts/pace_chart.py` for deterministic, offline calculations and exports. It requires Python 3.10+ and the standard library only. Resolve script paths relative to this skill folder, regardless of the user's working directory.

## Inspect the route first

```bash
python3 <skill-dir>/scripts/pace_chart.py inspect <race.gpx>
```

Prefer CPs embedded in the GPX. Recognized waypoint names/types and named route points supply the stations; ordinary turns and landmarks are not automatically included. Start and finish are added when absent; a shared start/finish venue is expanded into two rows. Keep the original CP numbers even if they have gaps.

Read the JSON inspection before requesting information. If multiple tracks exist, select the intended 1-based `track_index`. Ask for manual CP names and cumulative distances only when embedded CPs are absent or unusable. Ambiguous named waypoints can instead be confirmed with `cp_selection`. Normalize user-provided CSV or pasted CP data into the JSON configuration.

For a loop, crossing, or out-and-back, confirm the intended route occurrence when multiple projections are plausible; record a GPX cumulative `distance_km` override. Confirm offsets over 100 m before enabling `allow_off_route`. Do not choose the nearest occurrence silently. See [references/configuration.md](references/configuration.md) for exact fields and examples.

## Set targets and assumptions

Obtain the intended finish target if it has not been supplied. A single `target` generates five columns at -60, -30, 0, +30, +60 minutes by default. Use `target_step_minutes` for another interval, or `targets` for the user's exact list, including a single-column chart.

Keep the default 5 m distance sampling and 20 m centered elevation smoothing unless the user requests alternatives or the source data warrants discussion. Finer interpolation does not create measurement detail. Do not replace these defaults with 25 m / 100 m.

Total targets include station rests. Rest defaults to zero; ask only when the user wants it modeled. Cutoffs are elapsed durations since the start; never invent them or infer them from CP numbers. For clock-time cutoffs, obtain the start time, date, and rollover information before conversion. Missing cutoffs remain visibly unchecked.

For manually supplied official distances, differences over `max(100 m, 0.5% of GPX distance)` require confirmation before `distance_alignment: "scale"`. The table continues to show GPX distances and preserves official labels separately.

The calculation is an independent interpretation of the archived article, with an explicit fatigue power curve. Read [references/model.md](references/model.md) when explaining the formula, adjusting model parameters, or discussing limitations. Do not claim equivalence to RunArt.Net's implementation or assess a runner's fitness from the GPX alone.

## Generate and verify

Write the selected assumptions to a JSON file, then run:

```bash
python3 <skill-dir>/scripts/pace_chart.py generate <race.gpx> \
  --config <race.json> --output-dir <output-dir>
```

The command writes `pace-chart.html`, `pace-chart.svg`, `pace-chart.csv`, and `pace-chart.json`. Existing outputs require another directory or the user's authorized `--overwrite`. The HTML and native SVG are self-contained; no network access is needed.

Check that CP order and names match the intended route, every final departure equals its finish target, and station rests are included exactly once. Review the reported warnings and any cutoff failures. For presentation-sensitive requests, render the SVG or print the HTML with available local tools and inspect long station names and target columns.

Deliver the output paths, route statistics, target list, smoothing settings, and material assumptions in the user's language; chart labels default to Chinese. Retain the attribution already included in the outputs. Describe the water column as a relative comparison, not an individual drinking prescription.
