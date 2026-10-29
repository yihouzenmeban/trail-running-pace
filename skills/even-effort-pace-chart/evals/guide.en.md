# Skills behavior evaluation

[简体中文](guide.md) | [English](guide.en.md)

This guide is for Skills maintainers. Normal chart generation does not require these materials. Run the commands below from the repository root.

## Cases and inputs

[cases.json](cases.json) provides seven cases with Chinese and English prompts. They cover defaults, start time independent of parenthesized display, explicit arrival display, disabling linear fatigue, explicit terrain adjustments, replacing an old target list, and retaining `0/false`. All cases use the synthetic [course.gpx](course.gpx) in the same directory.

## Procedure

1. Open an independent agent session for each case and language, and load `even-effort-pace-chart`.
2. Supply only that language's prompt, the route, and the case's `selected_config` if present. Do not supply expected results.
3. Retain the configuration actually written by the agent and its execution trace, then run:

```bash
python3 skills/even-effort-pace-chart/evals/evaluate.py \
  --case start_does_not_select_arrival --config outputs/candidate.json
```

Set `--case` to the case ID and `--config` to the configuration actually produced in that session. Exit code `0` means the configuration matches the case, `1` means it does not, and `2` indicates a command or file error.

## Manual review and records

Review the trace for route inspection, unnecessary questions about defaults, the requested files actually being generated, and the verification summary being read. Record the model version, language, case ID, checker result, and manual review outcome.

The checker runs offline without calling an agent. It does not verify execution traces or actual files. Unit tests establish that the checker accepts correct configurations and rejects incorrect ones, not that natural-language evaluations have passed.
