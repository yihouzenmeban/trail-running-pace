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

Compute horizontal cumulative distance with the haversine formula on a sphere of radius 6,371,008.8 m. Elevation does not lengthen the geometric distance.

1. Interpolate elevation linearly along cumulative distance, every **5 m**, plus the exact endpoint.
2. At each sample, average the resampled piecewise-linear elevation over a **20 m full-width centered window** (10 m each side).
3. Clip windows at the course boundaries and divide by their actual width. Integration uses exact trapezoid areas; this is a distance-weighted average, not a point-count average.
4. Independently average the same resampled elevations over a **100 m full-width centered window** for cumulative ascent/descent. This is controlled by `ascent_smoothing_m`, not by the display setting `smoothing_m`.
5. Insert CP boundary elevations into each curve. Sum positive/negative changes on the statistical curve for ascent/descent; use the detailed curve for thumbnails and slope bins. Both curves are filtered over the whole route before any station split, so splitting at CPs cannot reset the filter or change route totals.

Settings are adjustable; 0 disables the corresponding smoothing. Interpolation cannot recover missing terrain detail; sparse points over 100 m apart produce a warning. The 5 m grid and 20 m display retain short features, while the independent statistical scale avoids counting every small oscillation toward total ascent. The integral of positive changes on the displayed curve therefore need not equal reported ascent. Statistical filtering can also suppress real short undulations; neither its scale nor matching another platform establishes ground truth. No external DEM, road classifier, or elevation correction is applied.

The supplied reference table for `examples/tiandi-liubai-100k/天地留白100K.gpx` contains eleven incoming-leg gains of 397, 394, 439, 666, 893, 583, 531, 403, 567, 233, and 220 m, summing to 5,326 m. With 5 m sampling, summing the 20 m curve gave 6,653 m; the independent 100 m statistical curve gives approximately 5,332 m with a mean absolute per-leg difference of 9.4 m. This is a comparison against one supplied reference, not a reproduction of COROS or RunArt.Net's internal algorithm. No gain is multiplied by a fitted correction factor.

Each segment's seven slope bins are weighted by horizontal distance. Boundaries, in percent, are `(-inf, -15]`, `(-15, -10]`, `(-10, -5]`, `(-5, 5)`, `[5, 10)`, `[10, 15)`, `[15, inf)`. The center bar is white; descent is on the left and ascent on the right. Segment profile thumbnails use independent horizontal and vertical scales and must not be compared as equal-scale maps.

## Equivalent distance

For a segment:

```text
E = horizontal_distance_km + ascent_m / 100 * ascent_km_per_100m
```

The coefficient defaults to 1 km per 100 m of ascent, following the article's common baseline. Downhill does not subtract equivalent distance. Steep descents and technical terrain can demand extra effort that this scalar model does not capture.

## Fatigue and finish targets

Let `r` be `fatigue_rate` (default 0.08), `E_total` the total equivalent distance, and `E_i` the cumulative equivalent distance through station i.

```text
b = 1 + log2(1 + r)
T_move = T_finish - sum(station_rest_seconds)
M_i = T_move * (E_i / E_total)^b
segment_moving_i = M_i - M_(i-1)
segment_eq_pace_i = segment_moving_i / segment_equivalent_km
segment_distance_pace_i = segment_moving_i / segment_horizontal_km
arrival_i = M_i + sum(rest before station i)
departure_i = arrival_i + rest_i
```

`r = 0` gives constant equivalent pace. With the default, average pace over a doubled equivalent distance changes by the factor `2^(b-1) = 1.08`. This is a power-curve parameterization, not a claim that the article's illustrated interval examples or the proprietary tool use these exact equations. The curve is normalized separately for each target, so every final departure is exactly that target before presentation rounding.

Rest is explicit and included once; no automatic extra delay or stop is inferred. Every target must exceed total rest. Time calculations retain floating-point precision; segment totals calculated from rounded display values may differ slightly.

The reference-style table displays cumulative departure durations truncated to full minutes. `secondary_display` selects the parenthesized value: default `"pace"` divides incoming segment moving seconds by horizontal kilometres; `"equivalent_pace"` divides by equivalent kilometres. Both round to seconds as `MM:SS`; equivalent pace is labeled “等强配速” in the chart. `"arrival_time"` instead adds cumulative arrival duration to `start_time`, showing local clock time before the current rest as `HH:MM`, truncated to minutes. Midnight rollover is marked “次日” or “+N天”, with no time-zone or daylight-saving conversion. Start time defaults to 06:00 and accepts an override as `HH:MM` or a full date/time; no race date is assumed when omitted. Pace modes omit parentheses at the start; arrival clock mode shows the gun time there.

All three modes preserve timing allocation and rest calculations. Legacy `pace_basis: "equivalent"` still selects equivalent pace when `secondary_display` is absent; the new field takes precedence. Both paces and cumulative arrival/departure durations retain full precision. CSV formatted cumulative durations continue to round to seconds.

Start time and the parenthesized display are independent; providing a start time still defaults to pace. Arrival clock time appears only when `secondary_display: "arrival_time"` is explicitly selected. Only SVG is exported by default; additional `output_formats` affect exported files without changing model calculations. CSV/JSON fields discussed here are exported when those formats are selected.

These columns are pre-race reference schedules. Switching to an adjacent column mid-race does not recompute the remaining schedule from the runner's current time, fatigue, or position.

## Water and uncertainty

Comparative segment water is `E / 10 * water_ml_per_10km`, defaulting to 700 mL per 10 equivalent kilometres as an article-inspired baseline. `segment_water_ml` belongs to the incoming leg. The displayed `water_ml` belongs to the next leg, so it is shifted up one station and becomes zero at the finish. It communicates relative segment demand. It is not an individual hydration, medical, or race-safety recommendation.

The input route alone cannot establish an achievable finish target. Terrain surface, steep descent load, weather, congestion, altitude response, runner fitness, nutrition, and recovery are not modeled. Missing race cutoffs remain unchecked. Route-derived totals can differ from organizer statistics because of geometry, elevation source, smoothing, and distance mapping.
