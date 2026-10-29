# Split-model evaluation

[简体中文](pacing-validation.md) | [English](pacing-validation.en.md)

This tool evaluates allocation across splits given a known finish duration, not finish capability. The finish is forced to match, so only segment and internal-checkpoint errors are scored. This is separate from [Skills behavior evaluation](guide.en.md).

## Input

Prepare local JSON. This example is synthetic. `distance_km` and `ascent_m` are **segment increments**, not cumulative values. Consecutive segments must cover the entire activity. Rest belongs to a segment's endpoint; the last segment must have zero rest.

```json
{
  "activities": [
    {
      "id": "training-example",
      "split": "train",
      "time_basis": "moving",
      "segments": [
        {"distance_km": 5, "ascent_m": 200, "seconds": 3000, "rest_seconds": 120},
        {"distance_km": 5, "ascent_m": 0, "seconds": 2400}
      ]
    },
    {
      "id": "validation-example",
      "split": "validation",
      "time_basis": "elapsed_unseparated",
      "segments": [
        {"distance_km": 5, "ascent_m": 100, "seconds": 2700},
        {"distance_km": 5, "ascent_m": 0, "seconds": 2500}
      ]
    }
  ]
}
```

- `moving`: `seconds` contains movement only; `rest_seconds` contains additional, confirmed endpoint rest, default 0. Do not supply total elapsed time as movement.
- `elapsed_unseparated`: `seconds` includes stops that cannot be separated reliably. This supports exploratory comparison only; `rest_seconds` must be zero to avoid double counting.
- Optional per-segment `terrain_factor` defaults to 1 and must be at least 1. Split segments at terrain boundaries rather than replacing work integration with a simple average factor.
- Each activity needs at least two segments. Distances and seconds must be finite and positive; ascent and rest are nonnegative. IDs must be unique; renaming the same activity does not make it independent.

Keep raw routes and observations outside the repository. Prefer official race CP records or activity records with separable timer stops. Training breaks, intervals, and photography are not fatigue. GPX timestamps alone do not justify classifying slow steep hiking as a stop. Use consistent elevation processing and document segmentation and missing-point handling.

## Run

```bash
python3 skills/even-effort-pace-chart/evals/evaluate_pacing.py \
  --observations /path/to/private-observations.json
```

Defaults compare legacy power at 0.08 with linear `fatigue_half_slowdown` values 0, 0.08, 0.16, 0.24, and 0.4. Supply `--candidates /path/to/candidates.json` for a JSON list of configurations. Only `fatigue_model`, the active model's fatigue parameter, and `ascent_km_per_100m` are accepted.

Output is aggregate JSON without activity IDs, coordinates, or per-activity details. Exit code 0 means evaluation completed; 2 means invalid input. No configurations, observations, or defaults are modified.

## Interpretation

Freeze the whole-activity split before inspecting results, for example older 80% for training and newer 20% for validation. Never randomly split segments from the same activity across sets. Each set requires at least one activity, but small samples are unstable. Repeated tuning against validation results requires a new independent test set.

| Output | Meaning |
| --- | --- |
| `selected_index` | Zero-based candidate selected solely by training `mean_segment_wape`; ties use input order |
| `mean_segment_wape` | Sum of absolute segment errors / total observed seconds per activity, averaged equally across activities; 0.1 means 10% |
| `mean_segment_mae_seconds` | Mean absolute segment error per activity, then averaged equally across activities |
| `mean_checkpoint_mae_seconds` | Mean absolute cumulative arrival error at internal checkpoints, excluding start and forced finish |
| `mean_checkpoint_mae_fraction` | Internal-checkpoint error / total observed seconds, averaged equally across activities |
| `time_basis_counts` | Activity counts for both time conventions; review mixed conventions separately |

Known rests are included once in predictions and observations and excluded from fatigue fitting. Unseparated stops contaminate curve errors. This evaluates timing allocation, not physiological truth of equivalent distance, and does not infer terrain or downhill coefficients. A better fit for one athlete is not sufficient evidence to change a public tool's defaults.
