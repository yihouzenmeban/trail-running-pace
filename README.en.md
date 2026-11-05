# Even-Effort Pace Chart Skills

[简体中文](README.md) | [English](README.en.md)

An independent community implementation inspired by 耐力学社's even-effort pacing approach. Before a race, turn GPX, KML, or FIT routes into checkpoint-based plans for multiple finish targets. After a race, compare a FIT activity with those plans to review cumulative differences, segment times, and terrain metrics. Invoke `even-effort-pace-chart` through an AI assistant or use the command line.

The approach draws on [《耐力科学｜体感一致配速表全面指南》](https://mp.weixin.qq.com/s/spYCP-upbqAZN0kzUm-0ng) by 耐力学社 / Pili（表哥）. This project independently implements equivalent-distance and fatigue curves; it is not an official RunArt.Net tool or output. See [sources and copyright](#sources-and-copyright).

## Preview

![Huizhou Ancient City 100K pace chart](examples/huizhou-gucheng-100k/pace-chart.svg)

| Example and notes | Pace charts | Activity comparisons |
| --- | --- | --- |
| [Huizhou Ancient City 100K](examples/huizhou-gucheng-100k/README.en.md): GPX planning and post-race FIT review | [GPX plans](examples/huizhou-gucheng-100k/pace-chart.svg) / [FIT-route plans](examples/huizhou-gucheng-100k/pace-chart-fit.svg) | [On the pre-race GPX](examples/huizhou-gucheng-100k/garmin-comparison.svg) / [On the recorded FIT](examples/huizhou-gucheng-100k/garmin-comparison2.svg) |
| [Dajingmen DGW100K](examples/大境门/DGW100K/README.en.md): reproducible from the public KML | [10–24 hours](examples/大境门/DGW100K/pace-chart.svg) / [15-hour plan](examples/大境门/DGW100K/15h/README.en.md) | — |
| [Dajingmen MGW50K](examples/大境门/DGW50K/README.en.md): plans use the public elevation-filled copy; includes pre-race-GPX and recorded-FIT post-race comparisons | [5–12.5 hours](examples/大境门/DGW50K/pace-chart.svg) / [Single 6:15 plan](examples/大境门/DGW50K/pace-chart-6h15m.svg) / [FIT-route plans](examples/大境门/DGW50K/pace-chart-fit.svg) | [On the pre-race GPX](examples/大境门/DGW50K/garmin-comparison.svg) / [On the recorded FIT](examples/大境门/DGW50K/garmin-comparison2.svg) |

Example notes include input provenance, configurations, files needed for reproduction, commands, and metric definitions.

## Installation and use

Every method requires **Python 3.10+**. GPX/KML pace charts use only the standard library; FIT inputs and activity comparisons need an [optional dependency](skills/even-effort-pace-chart/references/comparison.en.md#prepare-inputs).

Choose one of two usage modes:

- **Use it in an AI assistant**: install the Skill, then invoke it in natural language. This is the best fit when you want the assistant to inspect the route, resolve ambiguities, and generate the chart.
- **Use the command line directly**: no Skill installation is needed. Clone the repository and run the scripts; see [command line use](#command-line-use).

### Use it in an AI assistant

#### Install the Skill (choose one)

1. **npx (recommended)**: requires Node.js, npm, and Git. Run this in your project directory:

   ```bash
   npx skills add yihouzenmeban/trail-running-pace --skill even-effort-pace-chart
   ```

   Follow the prompts to select your AI assistant. The default installation is project-level; add `-g` for a user-level installation, which can be run from any directory.

2. **Manual installation**: does not require Node.js. Download the versioned ZIP from [GitHub Releases](https://github.com/yihouzenmeban/trail-running-pace/releases) and extract `even-effort-pace-chart/`; if you already cloned the repository, you can copy `skills/even-effort-pace-chart/` instead. Copy the entire `even-effort-pace-chart/` directory into your assistant's skills directory. The directory contains everything needed at runtime; it does not depend on repository examples or the source article.

3. **WorkBuddy**: if you use WorkBuddy, install it from the sharing page instead; you do not need the npx or manual steps above.

   1. Open the [WorkBuddy Skill sharing page](https://www.workbuddy.cn/share/asset?shareCode=VxFVK8iJONQ7o2r3K9ffpU&sig=q3nO3wLULv--gGj0), then follow the prompts to install it in the WorkBuddy client.
   2. Confirm that the Skill is enabled in the installed skills list.

#### First use

After installation, prepare a GPX, KML, or FIT route (or start with the [public example](examples/huizhou-gucheng-100k/README.en.md)), then give your assistant the route path and finish target. In assistants that support `$name` invocation, use:

```text
$even-effort-pace-chart
Generate an even-effort pace chart from race.gpx with a 14-hour finish target,
writing to output/my-race/.
```

You can also name `even-effort-pace-chart` in a natural-language request.

Defaults:

- The target expands to five plans centered on it: two 30-minute steps before and after. For example, a 14:00 target produces 13:00, 13:30, 14:00, 14:30, and 15:00. These are finish durations, not clock times.
- The default start is 06:00. Supplying a start time only affects clock-time conversion; it does not change the parenthesized segment pace to an arrival time.
- Output is SVG only, with the completed segment pace in parentheses and Chinese chart labels.
- Embedded CPs are preferred. When they are missing or unusable, use a manual CP list instead (the two cannot be mixed). FIT routes require manual CPs.

Default water amounts are calculated from equivalent distance for leg comparison only; they are not personal hydration advice. To plan water around weather and personal needs, ask your assistant. It will request the missing race date and start time, drinking experience, carrying capacity, and station water availability, then calculate from your confirmed drinking rate and leg times. Weather only helps confirm the rate; the program does not adjust it automatically. See [water and weather](skills/even-effort-pace-chart/references/configuration.en.md#time-based-water-planning).

### Command line use

No Skill installation is needed. Clone the repository first:

```bash
git clone https://github.com/yihouzenmeban/trail-running-pace.git
cd trail-running-pace
```

Run the following commands from the repository root. Save this as `race.json`:

```json
{
  "name": "My race",
  "target": "14:00"
}
```

`target` is a finish duration (14 hours here), not a start time.

Inspect the public example route, then generate the chart:

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py inspect \
  'examples/huizhou-gucheng-100k/徽州古城100K.gpx'

python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  'examples/huizhou-gucheng-100k/徽州古城100K.gpx' \
  --config race.json --output-dir output/my-race
```

This produces five finish targets (13:00, 13:30, 14:00, 14:30, and 15:00; all are finish durations) and writes the chart to `output/my-race/pace-chart.svg`. `output/` is Git-ignored; use `--overwrite` to replace existing results.

`inspect` only reports route, CP, and diagnostic information; it does not write files, and `generate` re-reads the route. When you switch to your own route, run `inspect` on that file first, resolve any route or CP ambiguities, then run `generate`.

Both usage modes share the same configuration. The [complete parameter table](skills/even-effort-pace-chart/references/configuration.en.md#parameters) lists every pace-chart setting, default, and value description, including targets, stations, ascent processing, exports, water, and weather. Specify them in natural language or in `race.json`. Activity-comparison command options are covered in the [comparison reference](skills/even-effort-pace-chart/references/comparison.en.md).

## Post-race activity comparison

![Huizhou Ancient City 100K: cumulative gap and selected segment times against the 16-hour plan](examples/huizhou-gucheng-100k/assets/comparison-preview.svg)

This excerpt uses the recorded FIT route and the 16-hour plan. The [full comparison](examples/huizhou-gucheng-100k/garmin-comparison2.svg) includes 15h, 16h, and 17h plans plus segment ascent and descent. The [Dajingmen MGW50K notes](examples/大境门/DGW50K/README.en.md#post-race-activity-comparison) also include both pre-race-GPX and recorded-FIT comparisons, showing how the route input changes the plans.

There are two ways to run the comparison:

**Use it in an AI assistant**: give your assistant the race route, pace configuration, and recorded FIT activity:

```text
Use even-effort-pace-chart to compare activity.fit with race.gpx and race.json.
Use exact targets of 15, 16, and 17 hours, include elapsed times between adjacent
checkpoints, and write to output/comparison/.
```

**Use the command line**: install the FIT dependency, then inspect and generate offline (run these commands from the root of the cloned repository):

```bash
python3 -m pip install -r skills/even-effort-pace-chart/scripts/requirements-comparison.txt

python3 skills/even-effort-pace-chart/scripts/compare_activity.py inspect race.gpx \
  --config race.json --fit activity.fit \
  --targets 15:00 16:00 17:00

python3 skills/even-effort-pace-chart/scripts/compare_activity.py generate race.gpx \
  --config race.json --fit activity.fit \
  --targets 15:00 16:00 17:00 --output-dir output/comparison
```

The default output is `garmin-comparison.svg`. FIT and single-activity FIT ZIP are supported without online credentials. `inspect` only reports activity totals, checkpoint matches, and diagnostics; it does not write files. Resolve ambiguous checkpoint matches before running `generate`. Use `--overwrite` to replace existing results. See the [activity comparison reference](skills/even-effort-pace-chart/references/comparison.en.md) for reading charts, platform totals, rebuilding routes from FIT, and optional Garmin downloads.

## Documentation

| Topic | Reference |
| --- | --- |
| All pace-chart parameters, defaults, and value descriptions | [Complete parameter table](skills/even-effort-pace-chart/references/configuration.en.md#parameters) |
| Exact targets, manual CPs, rests, cutoffs, and exports | [Configuration and CLI](skills/even-effort-pace-chart/references/configuration.en.md) |
| Water amounts, personal rates, and weather forecasts | [Water and weather](skills/even-effort-pace-chart/references/configuration.en.md#time-based-water-planning) |
| KML heights, FIT device distance, and checkpoint requirements | [KML input](skills/even-effort-pace-chart/references/configuration.en.md#kml-input) / [FIT route input](skills/even-effort-pace-chart/references/configuration.en.md#fit-route-input) |
| Activity comparisons, delta signs, passage matching, and Garmin retrieval | [Activity comparison](skills/even-effort-pace-chart/references/comparison.en.md) |
| Equivalent distance, fatigue curves, distance, and elevation processing | [Model and limitations](skills/even-effort-pace-chart/references/model.en.md) |
| Why no averaging + 10 m is the default, and how to switch | [Ascent methods and historical experiments](skills/even-effort-pace-chart/references/ascent-options.en.md) |
| AI assistant workflow | [SKILL.md](skills/even-effort-pace-chart/SKILL.md) |

Ascent statistics and display smoothing are independent. Results depend on source elevations and processing parameters and may differ from event or other platform statistics.

## Development and tests

Run the Skill functionality tests and release workflow tests from the repository root:

```bash
python3 -m unittest discover -s skills/even-effort-pace-chart/tests -v
python3 -m unittest discover -s .github/tests -v
```

Skill tests cover route processing, pacing, and activity comparisons. Real-course tests are skipped when the Skills package is copied without `examples/`. See the [behavior evaluation guide](skills/even-effort-pace-chart/evals/guide.en.md) for natural-language cases and manual review, or the [development article](docs/articles/从配速表到百公里复盘.md) for the project story in Chinese.

When a commit affecting `skills/even-effort-pace-chart/` is pushed to `main`, the [release workflow](.github/workflows/release-skill.yml) runs the release tests, increments the patch version in both metadata files, and creates a version commit on `main`, a tag, and a GitHub Release with a ZIP containing only the Skill directory. Changes to Skill reference documents also trigger this workflow; sync the generated version commit before continuing development.

## Sources and copyright

The [article and illustration archive](docs/reference/) preserves the original source and copyright notice. Rights remain with their respective holders; use of those materials is subject to the original notice. Race-route and activity-comparison provenance is listed in each example's notes.
