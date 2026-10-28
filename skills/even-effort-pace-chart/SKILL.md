---
name: even-effort-pace-chart
description: Convert a GPX or KML race route into an even-effort trail running pace chart with checkpoint splits, elevation profiles, and multiple finish targets. Use when planning race pacing from GPX/KML or generating HTML, SVG, CSV, and JSON pace tables.
---

# Even-Effort Pace Chart

Use `scripts/pace_chart.py` for deterministic, offline calculations and exports. It requires Python 3.10+ and the standard library only. Resolve script paths relative to this skill folder, regardless of the user's working directory.

Read supporting references in the user's language, loading only the needed version: Chinese [configuration](references/configuration.md) and [model](references/model.md), or English [configuration](references/configuration.en.md) and [model](references/model.en.md).

## Inspect the route first

```bash
python3 <skill-dir>/scripts/pace_chart.py inspect <race.gpx-or-kml>
```

Prefer CPs embedded in the input. GPX waypoints/named route points and KML named Point placemarks supply candidates; ordinary turns and landmarks are not automatically included. Start and finish are added when absent; a shared start/finish venue is expanded into two rows. Keep the original station names and numbers even if they have gaps.

Read the JSON inspection before requesting information. If multiple tracks exist, select the intended 1-based `track_index`. KML supports LineString and gx:Track, including nested containers; separate lines remain separate selections. KMZ and remote NetworkLink routes are not supported. Ask for manual CP names and cumulative distances only when embedded CPs are absent or unusable. Ambiguous named waypoints can instead be confirmed with `cp_selection`. Normalize user-provided CSV or pasted CP data into the JSON configuration.

KML route coordinates need explicit altitudes. An absolute altitude mode is accepted directly. When altitudeMode is omitted or clampToGround, verify the supplied heights are suitable before using `inspect --use-kml-altitudes` and recording `use_kml_altitudes: true` in the configuration. This uses the raw heights with a warning; it does not fetch terrain or correct a vertical datum. Relative or sea-floor modes must be re-exported with absolute elevations. Never fill missing route altitudes with zero.

For a loop, crossing, or out-and-back, confirm the intended route occurrence when multiple projections are plausible; record a cumulative input-route `distance_km` override. Confirm offsets over 100 m before enabling `allow_off_route`. Do not choose the nearest occurrence silently. See the configuration reference in the user's language for exact fields and examples.

## Set targets and assumptions

Obtain the intended finish target if it has not been supplied. A single `target` generates five columns at -60, -30, 0, +30, +60 minutes by default. Use `target_step_minutes` for another interval, or `targets` for the user's exact list, including a single-column chart.

Keep 5 m distance sampling and 20 m centered smoothing for the displayed profile and slope bins. Cumulative ascent/descent use a separate `ascent_smoothing_m` window, default 100 m, on the same 5 m grid. This suppresses accumulated small oscillations while preserving a detailed display. Do not confuse the two scales or claim that interpolation adds measurement accuracy. Change the recorded parameters when the source data or a known reference warrants it; never rescale computed climbs to force a desired total.

Total targets include station rests. Rest defaults to zero; ask only when the user wants it modeled. `start_time` defaults to local 06:00 and accepts `HH:MM` or a full local date/time override; it does not change elapsed targets. Do not infer a race date when none is supplied. Cutoffs are elapsed durations since the start; never invent them or infer them from CP numbers. For clock-time cutoffs, confirm the actual start time, date, and rollover information before conversion. Missing cutoffs remain unchecked in JSON/CSV and produce CLI warnings; omit cutoff details from station cells when none are supplied.

Use `secondary_display` to select the parenthesized chart value: `"pace"` (default) for horizontal-distance segment pace, `"equivalent_pace"` for equivalent-distance segment pace (labeled 等强配速), or `"arrival_time"` for local arrival clock time before the current station's rest. Arrival clock mode uses the default 06:00 unless overridden. It includes the gun time at the start and marks midnight rollover as 次日 or +N天, without time-zone or daylight-saving conversion. Primary times remain elapsed departures. Legacy `pace_basis: "equivalent"` selects equivalent pace when `secondary_display` is absent; the explicit new field takes precedence.

For manually supplied official distances, differences over `max(100 m, 0.5% of route distance)` require confirmation before `distance_alignment: "scale"`. The table continues to show route-derived distances and preserves official labels separately.

The calculation is an independent interpretation of the archived article, with an explicit fatigue power curve. Read the model reference in the user's language when explaining the formula, adjusting model parameters, or discussing limitations. Do not claim equivalence to RunArt.Net's implementation or assess a runner's fitness from the route alone.

## Generate and verify

Write the selected assumptions to a JSON file, then run:

```bash
python3 <skill-dir>/scripts/pace_chart.py generate <race.gpx-or-kml> \
  --config <race.json> --output-dir <output-dir>
```

The command writes `pace-chart.html`, `pace-chart.svg`, `pace-chart.csv`, and `pace-chart.json`. Existing outputs require another directory or the user's authorized `--overwrite`. The HTML and native SVG are self-contained; no network access is needed. Use the reference race-table layout: white background, gray rules, black slope/profile graphics, yellow distance, red ascent, green descent, blue water, station names, and target columns. Water at a station is for the next leg; finish water is zero. Cumulative times display hours/minutes with the selected secondary value in parentheses. Both pace measures and elapsed arrival/departure seconds remain in CSV/JSON.

Check that CP order and names match the intended route, every final departure equals its finish target, and station rests are included exactly once. Review the reported warnings and any cutoff failures. For presentation-sensitive requests, render the SVG or print the HTML with available local tools and inspect long station names and target columns.

Keep the visible charts limited to the heading and table, with no explanatory footer. Show cutoff information in station cells only when supplied. Retain source attribution in document metadata and JSON.

Deliver the output paths, route statistics, target list, smoothing settings, and material assumptions in the user's language; chart labels default to Chinese. Describe the water column as a relative comparison, not an individual drinking prescription.
