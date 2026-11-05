# Skills behavior evaluation

[简体中文](guide.md) | [English](guide.en.md)

This guide is for Skills maintainers. Normal chart generation does not require these materials. Run the commands below from the repository root.

## Cases and inputs

[cases.json](cases.json) provides seven `cases` with Chinese and English prompts. They cover defaults, start time independent of parenthesized display, explicit arrival display, replacing an old target list, retaining `0/false`, time-based water, and SVG-only export. `manual_review_cases` adds an interactive weather-preview and confirmation scenario. All cases use the synthetic [course.gpx](course.gpx) in the same directory.

## Procedure

1. Open an independent agent session for each item in `cases` and each language, and load `even-effort-pace-chart`.
2. Supply only that language's prompt, the route, and the case's `selected_config` if present. Do not supply expected results.
3. Retain the configuration actually written by the agent and its execution trace, then run:

```bash
python3 skills/even-effort-pace-chart/evals/evaluate.py \
  --case start_does_not_select_arrival --config outputs/candidate.json
```

Set `--case` to the case ID and `--config` to the configuration actually produced in that session. Exit code `0` means the configuration matches the case, `1` means it does not, and `2` indicates a command or file error.

## Manual review and records

Review the trace for route inspection, unnecessary questions about defaults, the requested files actually being generated, and the verification summary being read. For the manual-weather case, also check that the description matches the user's confirmed conditions; the checker validates the source, confirmation, and a non-empty description, but not its meaning. Record the model version, language, case ID, checker result, and manual review outcome.

Run `manual_review_cases` in separate sessions and review them manually; do not pass them to the configuration checker. For the weather preview, verify the date, time zone, and reference target. If the forecast succeeds, check that the agent presents it and waits for the user's confirmation of the weather and personal rate, without generating files or inventing values first. After the evaluator confirms them, check that the agent reuses the complete forecast snapshot and generates the chart. If the forecast is unavailable, the agent should explain that and wait for user-confirmed manual conditions.

The checker runs offline without calling an agent. It does not verify execution traces or actual files. Unit tests establish that the checker accepts correct configurations and rejects incorrect ones, not that natural-language evaluations have passed.
