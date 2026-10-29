#!/usr/bin/env python3
"""Compare pacing models on independent activity splits; read local JSON, emit aggregate JSON."""

import argparse
import json
from pathlib import Path
from statistics import mean
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pace_chart as pace


DEFAULT_CANDIDATES = [
    {"fatigue_model": "legacy_power", "fatigue_rate": .08},
    *({"fatigue_model": "linear", "fatigue_half_slowdown": half}
      for half in (0, .08, .16, .24, .4)),
]


def observations(data: dict) -> list[dict]:
    pace.keys(data, {"activities", "notes"}, "observations")
    items = data.get("activities")
    if not isinstance(items, list) or not items:
        raise pace.InputError("activities must be a non-empty list")
    seen, result = set(), []
    for item in items:
        pace.keys(item, {"id", "split", "time_basis", "segments"}, "activity")
        identity = item.get("id")
        if not isinstance(identity, str) or not identity.strip() or identity in seen:
            raise pace.InputError("activity id must be non-empty and unique across both splits")
        seen.add(identity)
        if item.get("split") not in ("train", "validation"):
            raise pace.InputError("activity split must be train or validation")
        if item.get("time_basis") not in ("moving", "elapsed_unseparated"):
            raise pace.InputError("time_basis must be moving or elapsed_unseparated")
        segments = item.get("segments")
        if not isinstance(segments, list) or len(segments) < 2:
            raise pace.InputError("Each activity needs at least two consecutive segments")
        normalized = []
        for segment in segments:
            pace.keys(segment, {"distance_km", "ascent_m", "seconds", "rest_seconds", "terrain_factor"},
                      "segment")
            values = {
                key: pace.number(segment.get(key, default), key, strictly_positive=key in
                                 ("distance_km", "seconds"), minimum=1 if key == "terrain_factor" else 0)
                for key, default in (("distance_km", None), ("ascent_m", None), ("seconds", None),
                                     ("rest_seconds", 0), ("terrain_factor", 1))
            }
            if item["time_basis"] == "elapsed_unseparated" and values["rest_seconds"]:
                raise pace.InputError("elapsed_unseparated already includes stops; rest_seconds must be zero")
            normalized.append(values)
        if normalized[-1]["rest_seconds"]:
            raise pace.InputError("The finish cannot have a post-finish rest")
        result.append({**item, "segments": normalized})
    if {item["split"] for item in result} != {"train", "validation"}:
        raise pace.InputError("Both train and validation need at least one independent activity")
    return result


def activity_errors(activity: dict, parameters: dict) -> dict:
    segments = activity["segments"]
    weights = [(s["distance_km"] + s["ascent_m"] / 100 * parameters["ascent_km_per_100m"])
               * s["terrain_factor"] for s in segments]
    total_weight = pace.number(sum(weights), "total effort", strictly_positive=True)
    total_seconds = pace.number(sum(s["seconds"] for s in segments), "total seconds", strictly_positive=True)
    accumulated_weight = predicted_previous = observed = 0.0
    segment_errors, checkpoint_errors = [], []
    for index, (segment, weight) in enumerate(zip(segments, weights)):
        accumulated_weight += weight
        predicted = total_seconds * pace.fatigue_fraction(accumulated_weight / total_weight, parameters)
        segment_errors.append(abs(predicted - predicted_previous - segment["seconds"]))
        observed += segment["seconds"]
        # Identical known rests cancel; adding them first would lose small timing errors.
        # The forced finish contributes no validation evidence.
        if index < len(segments) - 1:
            checkpoint_errors.append(abs(predicted - observed))
        predicted_previous = predicted
    return {
        "segment_wape": sum(error / total_seconds for error in segment_errors),
        "segment_mae_seconds": mean(segment_errors),
        "checkpoint_mae_seconds": mean(checkpoint_errors),
        "checkpoint_mae_fraction": mean(checkpoint_errors) / total_seconds,
    }


def compare(data: dict, candidates: list[dict]) -> dict:
    activities = observations(data)
    if not isinstance(candidates, list) or not candidates:
        raise pace.InputError("candidates must be a non-empty list")
    results = []
    for candidate in candidates:
        pace.keys(candidate, {"fatigue_model", "fatigue_rate", "fatigue_half_slowdown",
                              "ascent_km_per_100m"}, "candidate")
        parameters = {
            **pace.fatigue_parameters(candidate),
            "ascent_km_per_100m": pace.number(candidate.get("ascent_km_per_100m", 1), "ascent_km_per_100m"),
        }
        result = {"configuration": candidate, "parameters": parameters}
        for split in ("train", "validation"):
            errors = [activity_errors(a, parameters) for a in activities if a["split"] == split]
            result[split] = {"mean_" + key: mean(row[key] for row in errors) for key in errors[0]}
        results.append(result)
    selected = min(range(len(results)), key=lambda i: results[i]["train"]["mean_segment_wape"])
    return {
        "schema_version": 1,
        "selection_metric": "train.mean_segment_wape",
        "selected_index": selected,
        "activity_counts": {split: sum(a["split"] == split for a in activities)
                            for split in ("train", "validation")},
        "time_basis_counts": {basis: sum(a["time_basis"] == basis for a in activities)
                              for basis in ("moving", "elapsed_unseparated")},
        "candidates": results,
        "limitations": [
            "Finish duration is supplied, not predicted; only segment allocation is evaluated.",
            "Activities are weighted equally; WAPE within an activity is total absolute error / total time.",
            "Unseparated elapsed times confound stops with fatigue. Training runs need not reflect race pacing.",
            "Keep the validation split fixed and unused for tuning. IDs must identify independent activities.",
            "A better fit on one athlete does not establish a universal default or causal fatigue model.",
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, help="JSON list of model configurations")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.observations.read_text(encoding="utf-8"))
        candidates = (json.loads(args.candidates.read_text(encoding="utf-8"))
                      if args.candidates else DEFAULT_CANDIDATES)
        print(json.dumps(compare(data, candidates), ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (pace.InputError, OSError, UnicodeError, json.JSONDecodeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
