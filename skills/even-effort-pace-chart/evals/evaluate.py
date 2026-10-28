#!/usr/bin/env python3
"""Check an agent-produced configuration offline; this does not invoke an agent."""

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "scripts"))
import pace_chart as pace

SUITE = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))


def evaluate(case_id: str, config: dict) -> dict:
    case = next(case for case in SUITE["cases"] if case["id"] == case_id)
    errors = []
    result = {"case": case_id, "passed": False, "errors": errors}
    try:
        plan = pace.build_plan(ROOT / "course.gpx", config)
    except (pace.InputError, OSError) as error:
        errors.append(str(error))
        return result
    expected_parameters = {**SUITE["default_parameters"], **case.get("expected_parameters", {})}
    for key, expected in expected_parameters.items():
        actual = plan["parameters"][key]
        if actual != expected:
            errors.append(f"parameters.{key}: expected {expected!r}, got {actual!r}")
    if plan["targets_seconds"] != SUITE["targets_seconds"]:
        errors.append(f"targets_seconds: expected {SUITE['targets_seconds']}, got {plan['targets_seconds']}")
    for key, expected in case.get("required_config", {}).items():
        if key not in config or config[key] != expected:
            errors.append(f"configuration.{key}: expected explicit {expected!r}")
    for key in case.get("forbidden_config", []):
        if key in config:
            errors.append(f"configuration.{key}: must be removed for this request")
    if [cp["id"] for cp in plan["checkpoints"]] != ["start", "wpt:1", "finish"]:
        errors.append("checkpoint selection must preserve the embedded CP1 and both endpoints")
    if any(cp["rest_seconds"] != 0 or cp["cutoff_seconds"] is not None for cp in plan["checkpoints"]):
        errors.append("no station rests or cutoffs were requested")
    result["summary"] = pace.plan_summary(plan)
    result["passed"] = not errors
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, choices=[case["id"] for case in SUITE["cases"]])
    parser.add_argument("--config", required=True, type=Path, help="Actual configuration written by the agent")
    args = parser.parse_args(argv)
    try:
        result = evaluate(args.case, json.loads(args.config.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
