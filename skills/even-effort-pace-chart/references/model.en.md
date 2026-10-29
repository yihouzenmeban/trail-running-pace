# Model, provenance, and limitations

[简体中文](model.md) | [English](model.en.md)

## Source

Conceptual reference: "耐力科学|体感一致配速表全面指南", 耐力学社 / Pili (表哥), published by 耐力學社 on 2025-08-26; the article credits 隆景体育.

Original: https://mp.weixin.qq.com/s/spYCP-upbqAZN0kzUm-0ng

The repository archive is `docs/reference/耐力科学_体感一致配速表全面指南.md`, with its illustrations under `docs/reference/assets/pace-chart/`. These paths are relative to the repository root. The Skills package remains usable when copied independently; it does not require the archive at runtime.

This is an independent implementation of the article's equivalent-distance and fatigue-curve ideas. The article does not expose RunArt.Net's full algorithm. The equations below are this implementation's explicit, reproducible choices; generated charts must not be represented as official RunArt.Net output. Preserve the source attribution included by the exporters. The article's original copyright statement remains in the repository archive; this project does not reinterpret the terms for third-party material.

## Input normalization

Both GPX and KML become the same ordered `(latitude, longitude, elevation)` profile before distance, smoothing, CP projection, and schedule calculation. Original timestamps do not determine the target schedule; distinct line geometries remain separate route selections rather than automatically concatenated segments. Supported formats, altitude modes, and explicit overrides are defined in the [configuration reference](configuration.en.md#kml-input). Permission to use coordinate heights does not establish that they are surveyed sea-level elevations.

## Distance and elevation

Compute horizontal cumulative distance with the haversine formula on a sphere of radius 6,371,008.8 m. Elevation does not lengthen geometric distance. Processing order: validate and deduplicate source points, handle isolated elevation spikes, optionally simplify horizontal geometry, build separate display and ascent curves, then split at CPs.

### Input quality and horizontal distance

The original horizontal path is retained by default. Only `distance_tolerance_m > 0` enables RDP simplification bounded by lateral deviation. Block anchors are retained approximately every 250 m, together with endpoints, closed loops, and points that reverse progress along a chord. Real turns smaller than the tolerance can still be simplified; removed distance is not proof of GPS drift.

Simplification changes horizontal geometry without discarding intermediate elevation observations. Each observation is located by its spatial projection onto the retained chord. Backward or coincident projections introduce extra anchors, keeping distances strictly increasing and preventing elevation from being moved across a CP. Elevation order is retained, and CPs are projected onto the processed geometry. Explicit cumulative distances use this processed distance basis too; recheck CPs after enabling simplification instead of reusing old projections.

With simplification disabled, a 5 m tolerance trial still diagnoses sensitivity. A reduction exceeding `max(10 m, 1% of original distance)` produces a warning without changing distance. GPX `hdop > 10`, `vdop > 20`, `fix=none/unknown`, and invalid quality values are diagnostic only; they do not automatically delete points. Missing quality fields do not establish accuracy. Timestamps may come from route-planning software, so they do not trigger automatic speed filtering.

### Elevation spikes

`elevation_spike_m` defaults to 30 m; 0 disables correction. An isolated interior point is corrected only when all of these conditions hold:

- Its residual from linear prediction between its neighbors reaches the configured threshold.
- The neighbors are at most 50 m apart, and both absolute adjacent grades exceed 200%.
- It is above both or below both neighbors, whose elevations differ by less than half the threshold.
- Neither adjacent point is also flagged as a potential spike.

Replace that elevation with the neighbors' linear prediction, recording indices, count, and a warning. This is conservative anomaly detection, not surveyed correction: endpoints, sustained steps, multi-point corruption, and low-amplitude noise are not automatically corrected. Very narrow real terrain may also satisfy the rule. Indices are zero-based within the sequence after consecutive duplicate coordinates are removed. Source files remain unchanged and their SHA is retained.

### Display curve and boundaries

Emit samples every **5 m** plus the exact endpoint. The default **20 m full-width centered window** computes a distance-weighted elevation average. Integration uses all vertices of the input polyline directly, avoiding the loss of between-grid peaks before averaging. Near either endpoint, shrink the window symmetrically and retain the endpoint height itself. Noise-free linear slopes consequently retain their full elevation change. A zero window performs linear interpolation only.

### Ascent and descent

Defaults are `ascent_method: "hysteresis"`, `ascent_threshold_m: 10`, and `ascent_smoothing_m: 0`:

1. Track running peaks and valleys directly on cleaned source elevation vertices, without window averaging. Do not substitute the display curve's 5 m sampling grid for source vertices, so short hills between grid points are retained.
2. Confirm a reversal only after a cumulative opposite change of at least 10 m. This is not a minimum adjacent-point difference, so gradual continuous climbs accumulate correctly.
3. Between confirmed extrema, build a monotone envelope at the same along-route distances. This suppresses minor reversals while retaining the source curve's plateaus and the location of major climbs.
4. Retain both endpoint heights and the initial/terminal extrema participating in a confirmed threshold span. Boundary fragments may therefore include subthreshold ascent/descent, but confirmed terrain is not erased and net elevation change is preserved. If the whole profile varies by less than the threshold, only its net start-to-end change remains.
5. Insert CP boundary heights into this curve and accumulate positive/negative changes. Filter globally before splitting; adding CPs does not reset the algorithm or change total ascent/descent.

No averaging and a 10 m threshold are an engineering tradeoff that retains source extrema while suppressing small reversals, not an accuracy guarantee or a community standard. Subthreshold round-trip undulations may be ignored, while elevation noise exceeding the threshold may still count as ascent. Do not infer elevation provenance or adjust filters automatically from file format, point density, or exporting software.

An explicit positive `ascent_smoothing_m` enables an independent full-width centered average; for example, 40 m means 20 m on each side. Average by distance and emit samples every 5 m before applying the reversal threshold, using the same integration and endpoint rules as the display curve. Averaging can suppress real short hills. An explicit `ascent_threshold_m: 0` disables only peak/valley filtering: with the default `ascent_smoothing_m: 0`, changes are summed directly at cleaned source vertices; explicitly enabled averaging remains active. Positive changes in the display curve need not sum to reported ascent.

Select the window method explicitly with `"ascent_method": "window", "ascent_smoothing_m": 100`; it ignores the peak/valley threshold. It retains the previous statistical approach while applying the new integration and boundary fixes, so it is not bit-for-bit legacy output. An old configuration containing only `ascent_smoothing_m: 100` now applies the default peak/valley filter after that window; add `ascent_method: "window"` to select the previous method.

### Examples and limitations

See [ascent methods and selection rationale](ascent-options.en.md) for the default choice and activity/route comparisons. Results depend on filtering scale; agreement with a reference is neither ground truth nor general calibration, and parameters must not be tuned solely to match a platform total.

For methodological comparisons, see [GPS Visualizer's elevation thresholds](https://www.gpsvisualizer.com/tutorials/elevation_gain.php), [GPSBabel's quality filters](https://www.gpsbabel.org/htmldoc-1.10.0/filter_discard.html), and [Strava's elevation FAQ](https://support.strava.com/en-us/articles/15402093-elevation-on-strava-faqs). This implementation's peak/valley envelope and defaults are independent choices, not reproductions of those tools.

Interpolation cannot recover missing terrain detail; original point gaps over 100 m produce a warning. No external DEM, road matching, or surveyed elevation correction is used. Filtering cannot establish true distance or ascent from the track alone; retain input provenance and parameters with the results.

Each segment's seven slope bins are weighted by horizontal distance. Boundaries, in percent, are `(-inf, -15]`, `(-15, -10]`, `(-10, -5]`, `(-5, 5)`, `[5, 10)`, `[10, 15)`, `[15, inf)`. The center bar is white; descent is on the left and ascent on the right. Segment profile thumbnails use independent horizontal and vertical scales and must not be compared as equal-scale maps.

## Equivalent distance

For a segment:

```text
E = horizontal_distance_km + ascent_m / 100 * ascent_km_per_100m
```

The coefficient defaults to 1 km per 100 m of ascent, consistent with the article and [ITRA's km-effort convention](https://itra.run/Files/News/PressReleases/DP_ITRA_2018_EN.pdf). A course difficulty measure does not validate split-time predictions. Downhill does not subtract equivalent distance; different profiles with identical distance and ascent receive the same base weight.

Explicit `terrain_sections` apply difficulty factors `f >= 1` over processed-route kilometre ranges. Uncovered ranges use 1. Integration respects range boundaries and elevation vertices:

```text
dW = f * (horizontal_distance_km + positive_elevation_change_m / 100 * ascent_km_per_100m)
```

`W` is the adjusted work used for timing, exported as `effort_distance_km` and `cumulative_effort_distance_km`. Base `eq_distance_km`, the equivalent-pace denominator, and water continue to use `E`. Factors do not add ascent twice and are never inferred automatically from GPX or grade. They redistribute a fixed finish target: increasing one section's factor leaves less time for other sections. They do not predict an extension of the target. A uniform factor over the entire route cancels during normalization.

Ranges are independent of CPs, may touch, and must not overlap. Adding a CP preserves existing stations' cumulative work and planned times. Official-distance alignment does not scale these ranges; use processed-route kilometres.

[Minetti et al.'s grade-cost experiment](https://pubmed.ncbi.nlm.nih.gov/12183501/) shows that downhill cost is not constant, but laboratory energy cost does not directly predict technical-trail speed. [Trail-race split research](https://pmc.ncbi.nlm.nih.gov/articles/PMC9680470/) also finds descent slowdown depends on race stage. This model therefore applies neither automatic downhill speed credits nor a universal descent penalty. Explicit terrain factors do not replace a full grade and individual descent-skill model.

## Fatigue and finish targets

The default is `fatigue_model: "linear"`. Let `h = fatigue_half_slowdown`, default 0.16: **the second half of adjusted work takes 16% more moving time than the first half**. This does not mean half the horizontal distance, total-race slowdown, or a 16% speed reduction. Rests are excluded from this ratio.

```text
a = 4 * h / (2 - h)
x_i = W_i / W_total
F(x) = (x + a*x*x/2) / (1 + a/2)
T_move = T_finish - sum(station_rest_seconds)
M_i = T_move * F(x_i)
segment_moving_i = M_i - M_(i-1)
segment_eq_pace_i = segment_moving_i / segment_equivalent_km
segment_distance_pace_i = segment_moving_i / segment_horizontal_km
arrival_i = M_i + sum(rest before station i)
departure_i = arrival_i + rest_i
```

Pace per unit of adjusted work is proportional to `1 + a*x`, finite and positive at the start. `h = 0` allocates time linearly in `W`: equivalent pace is constant without terrain adjustments, but varies with terrain factors when they are supplied. The valid range `0 <= h <= 1` is a computational bound, not a recommended personal range.

The default 0.16 preserves the old default curve's half-time ratio while redistributing time within each half. This is an engineering compatibility choice, not a fit to personal training samples. For 100 flat kilometres in 10 hours without stops, the first kilometre is about 5:07/km, versus 3:36/km with the old curve. The default linear curve's terminal/initial pace-per-work ratio is about 1.348, not 1.16.

`h` does not automatically change with target duration, course length, or athlete ability; different targets share the same relative curve. A route alone cannot determine an individual's fatigue parameter. Rests reduce the movement budget without modeling recovery. The model does not simulate finishing sprints, darkness, or descent-specific fatigue. Tools such as [ultraPacer](https://www.ultrapacer.com/docs/models) separate grade, terrain, and pacing strategy; their design does not validate this project's coefficients.

### Legacy power curve and migration

Explicit `fatigue_model: "legacy_power"` uses `b = 1 + log2(1 + fatigue_rate)` and `F(x) = x^b`, with legacy default rate 0.08. An old configuration supplying only `fatigue_rate` automatically selects this model and warns, preserving its meaning. Rate 0.08 makes the second half take 16% longer. Starting pace tends to zero, making short opening splits potentially too fast. To migrate, remove `fatigue_rate` and choose `fatigue_half_slowdown`. Model-specific parameters cannot be mixed. Legacy `fatigue_rate: 0` still disables fatigue progression.

Riegel's performance relationship describes sustainable performances across distances; it does not establish `x^b` as a within-race cumulative-time curve. See [research on power laws and endurance performance](https://link.springer.com/article/10.1007/s00421-023-05274-5). The legacy curve also does not promise to reproduce the source article's interval examples.

### Calibration and validation

Every target is normalized separately to finish exactly on target. This is an arithmetic constraint, not prediction accuracy. Use the [split-model evaluation](../evals/pacing-validation.en.md) to compare internal CP and segment errors, separating whole activities into training and validation sets and distinguishing moving from unseparated elapsed time. Fitting and evaluating on the same activities is not independent validation; a better fit for one athlete must not automatically replace the global default.

Rest is explicit and included once; no automatic extra delay or stop is inferred. Every target must exceed total rest. Time calculations retain floating-point precision; segment totals calculated from rounded display values may differ slightly.

The reference-style table displays cumulative departure durations truncated to full minutes. `secondary_display` selects the parenthesized value: default `"pace"` divides incoming segment moving seconds by horizontal kilometres; `"equivalent_pace"` divides by equivalent kilometres. Both round to seconds as `MM:SS`; equivalent pace is labeled “等强配速” in the chart. `"arrival_time"` instead adds cumulative arrival duration to `start_time`, showing local clock time before the current rest as `HH:MM`, truncated to minutes. Midnight rollover is marked “次日” or “+N天”, with no time-zone or daylight-saving conversion. Start time defaults to 06:00 and accepts an override as `HH:MM` or a full date/time; no race date is assumed when omitted. Pace modes omit parentheses at the start; arrival clock mode shows the gun time there.

All three modes preserve timing allocation and rest calculations. Legacy `pace_basis: "equivalent"` still selects equivalent pace when `secondary_display` is absent; the new field takes precedence. Both paces and cumulative arrival/departure durations retain full precision. CSV formatted cumulative durations continue to round to seconds.

Start time and the parenthesized display are independent; providing a start time still defaults to pace. Arrival clock time appears only when `secondary_display: "arrival_time"` is explicitly selected. Only SVG is exported by default; additional `output_formats` affect exported files without changing model calculations. CSV/JSON fields discussed here are exported when those formats are selected.

These columns are pre-race reference schedules. Switching to an adjacent column mid-race does not recompute the remaining schedule from the runner's current time, fatigue, or position.

## Water and uncertainty

Comparative segment water is `E / 10 * water_ml_per_10km`, defaulting to 700 mL per 10 equivalent kilometres as an article-inspired baseline. `segment_water_ml` belongs to the incoming leg. The displayed `water_ml` belongs to the next leg, so it is shifted up one station and becomes zero at the finish. It communicates relative segment demand. It is not an individual hydration, medical, or race-safety recommendation.

The input route alone cannot establish an achievable finish target. Terrain uses explicit factors only; steep descent load, weather, congestion, altitude response, runner fitness, nutrition, and recovery are not modeled automatically. Missing race cutoffs remain unchecked. Route-derived totals can differ from organizer statistics because of geometry, elevation source, smoothing, and distance mapping.
