# GPX / KML 体感一致配速表 Skill

[简体中文](README.md) | [English](README.en.md)

将 GPX 或 KML 比赛轨迹转换成按 CP 分段的越野跑配速表，同时比较多组目标完赛时间。既可作为 `even-effort-pace-chart` Skill 使用，也可直接通过命令行生成。

- 默认读取轨迹内的 CP；缺少可用站点时再提供人工 CP 列表。
- 单个目标时间默认展开五组方案，相邻间隔 30 分钟；支持自定义间隔或目标列表。
- 展示分段距离、爬升、下降、坡度分布、海拔肖像和下一段参考水量。
- 支持站点停留和关门时间；未提供关门时间时，位置列不显示关门信息。
- 默认仅导出 SVG；可通过配置选择 HTML、CSV、JSON 等其他格式。

![天地留白100K 配速表示例](examples/tiandi-liubai-100k/pace-chart.svg)

## 环境要求

Python 3.10 或更高版本，仅使用标准库，无需安装额外依赖或配置在线服务。轨迹点需要包含坐标和海拔，GPX/KML 根据 XML 根元素自动识别。

## 作为 Skill 使用

将 `skills/even-effort-pace-chart/` 整个目录复制到所用代理的技能目录，保留其中的 `SKILL.md`、`agents/`、`scripts/` 和 `references/`，然后在对话中调用：

```text
$even-effort-pace-chart
用 examples/tiandi-liubai-100k/天地留白100K.gpx 生成体感一致配速表，
目标完赛时间 14 小时，相邻方案间隔 30 分钟，出发时间早上六点，输出到 output/my-race/。
```

Skill 会先检查轨迹和 CP，再根据目标时间及配置生成结果。上面的请求默认只输出 SVG，括号内显示区间配速；提供出发时间不会切换为到达时间。也可以提供 KML、自定义目标列表、各站停留时间和关门时间。图表标签默认为中文。

## 命令行快速开始

以下命令在仓库根目录执行。先检查示例轨迹和 CP：

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py inspect \
  'examples/tiandi-liubai-100k/天地留白100K.gpx'
```

使用示例配置生成 12、13、14、15、16 小时五组方案：

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  'examples/tiandi-liubai-100k/天地留白100K.gpx' \
  --config examples/tiandi-liubai-100k/config.json \
  --output-dir output/tiandi-liubai-100k
```

输出写入 `output/`，该目录已加入 Git 忽略规则。需要替换已有结果时，在命令后加 `--overwrite`。

完整示例保存在 `examples/tiandi-liubai-100k/`，包含 GPX、配置和四种导出结果；示例配置显式设置 `output_formats` 为全部四种格式，普通配置默认仅导出 SVG。轨迹约 101.25 km，当前默认参数下累计爬升约 5,332 m。

### KML 示例

支持 LineString、gx:Track 和命名 Point 地标；多条路线通过 `track_index` 选择。KML 轨迹必须带高度，`altitudeMode` 为 `absolute` 时可直接使用。对于省略模式或 `clampToGround` 的文件，确认原始坐标高度适合计算后，检查时添加 `--use-kml-altitudes`，生成配置中添加 `"use_kml_altitudes": true`。工具会记录告警，不会填零、联网补海拔或将相对地面高度换算为海拔。不支持 KMZ 或远程 NetworkLink。

大境门示例已在配置中明确选择站点和原始高度：

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py inspect \
  'examples/大境门/2026京东大境门古长城越野赛by UTMB®DGW100K.kml' \
  --use-kml-altitudes

python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  'examples/大境门/2026京东大境门古长城越野赛by UTMB®DGW100K.kml' \
  --config 'examples/大境门/config.json' \
  --output-dir output/dajingmen
```

`examples/大境门/` 包含原始 KML、配置及四种结果。该文件未声明高度模式；示例配置显式采用坐标高度，并通过 `cp_selection` 选择 D1–D9、SP1 和共用起终点，排除重复端点。24 小时仅为示范目标，自动生成 23:00 至 25:00 五组方案。路线测算约 99.69 km、爬升约 3,635 m，未与赛事官方统计校准。

### 输出文件

默认仅生成 `pace-chart.svg`。如需额外导出，在比赛配置中加入以下字段；数组也可以只选择其中一种格式：

```json
{
  "output_formats": ["svg", "html", "csv", "json"]
}
```

| 文件 | 用途 |
| --- | --- |
| `pace-chart.html` | 浏览器离线查看，支持横向打印 |
| `pace-chart.svg` | 独立矢量表，适合预览、缩放和分享 |
| `pace-chart.csv` | 在表格软件中处理各 CP、各目标的时间数据 |
| `pace-chart.json` | 保留完整计算精度、参数、来源和告警 |

## 配置自己的比赛

将以下配置保存为 `race.json`：

```json
{
  "name": "我的比赛",
  "target": "14:00",
  "target_step_minutes": 30,
  "start_time": "2026-10-31 06:00"
}
```

将 `race.gpx` 替换为自己的 GPX 或 KML 路径：

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  race.gpx --config race.json --output-dir output/my-race
```

这份配置生成 13:00、13:30、14:00、14:30、15:00 五组方案。若要指定准确的目标列表，用 `targets` 替换 `target`：

```json
{
  "targets": ["12:00", "14:00", "16:00"]
}
```

| 常用参数 | 默认值 | 说明 |
| --- | --- | --- |
| `target` / `targets` | 必须提供其一 | 中心目标或明确的目标列表，时长支持 `H:MM`、`H:MM:SS`，可超过 24 小时 |
| `target_step_minutes` | `30` | 单个目标展开五组时的相邻间隔 |
| `start_time` | `"06:00"` | 本地发枪时间，可填 `HH:MM` 或完整日期时间；主行仍为比赛经过时长 |
| `secondary_display` | `"pace"` | 括号内显示内容：`"pace"` 配速、`"equivalent_pace"` 等强配速、`"arrival_time"` 到达钟点 |
| `output_formats` | `["svg"]` | 输出格式列表，可选 `"svg"`、`"html"`、`"csv"`、`"json"` |
| `pace_basis` | `"distance"` | 兼容旧配置：`"equivalent"` 对应等强配速；显式设置 `secondary_display` 优先 |
| `sample_m` | `5` | 沿距离插值的间隔，单位米 |
| `smoothing_m` | `20` | 海拔肖像与坡度分布的居中平滑窗口全宽，单位米 |
| `ascent_smoothing_m` | `100` | 累计爬升、下降的独立统计窗口全宽，单位米 |
| `use_kml_altitudes` | `false` | 显式采用未声明高度模式或 clampToGround 的 KML 坐标高度 |
| `checkpoint_overrides` | 不覆盖 | 按候选点 ID 设置名称、停留分钟数 `rest_minutes`、关门时长 `cutoff` 等 |
| `checkpoints` | 从轨迹读取 | 没有可用内嵌 CP 时，手动提供名称和累计公里数 |

目标完赛时间包含站点停留。关门时间按发枪后经过时长填写；环线、折返或偏离轨迹的 CP 可能需要明确确认位置。

“目标完赛时间 5 小时，相邻方案间隔 30 分钟，出发时间早上六点”对应的配置如下：

```json
{
  "target": "05:00",
  "target_step_minutes": 30,
  "start_time": "06:00",
  "secondary_display": "pace",
  "output_formats": ["svg"]
}
```

未提供 `start_time` 时默认早上六点发枪，不指定比赛日期；可用 `"07:30"` 或完整日期时间覆盖。出发时间与括号内容独立；只有明确要求显示到达时间时才设置 `secondary_display: "arrival_time"`。默认配速按区间水平距离计算，等强配速按区间等效距离计算，均仅含移动时间。到达钟点使用本站停留前的时间，跨日显示“次日”或“+N天”；三种展示方式均不改变时间分配。

完整字段、人工 CP 和关门时间示例见[配置文档](skills/even-effort-pace-chart/references/configuration.md)，计算公式与平滑方案见[模型文档](skills/even-effort-pace-chart/references/model.md)。

所有可选参数都按“当前明确要求 > 指定使用的配置 > 脚本默认值”处理。未指定的字段省略，不从示例或无关任务继承；合法的 `0` 和 `false` 会保留，`null` 或空字符串不能通用地代替默认值。复用配置并将目标列表改成中心目标时，应删除旧 `targets`，避免其优先于新 `target`。必需的目标时间和有歧义的轨迹、站点仍需明确提供。

## 开发与测试

```bash
python3 -m unittest discover -s skills/even-effort-pace-chart/tests -v
```

完整仓库会执行 GPX/KML 合成轨迹测试，以及天地留白 100K 和大境门 KML 真实赛道回归测试；单独复制 Skill、未携带 examples 时，真实赛道测试会跳过。

自然语言评测用例见 [evals/cases.json](skills/even-effort-pace-chart/evals/cases.json)，覆盖默认值、出发时间与括号内容独立、明确到达时间、替换旧目标列表和保留 `0/false`。每个用例提供中英文提示词，使用同目录的 `course.gpx` 合成轨迹。

评测时为每个用例和语言开启独立 AI 会话，加载 Skill，只提供该语言的提示词、轨迹和用例中的 `selected_config`（若有），不要提供预期结果。保留 AI 实际写出的配置与执行记录，再运行检查器：

```bash
python3 skills/even-effort-pace-chart/evals/evaluate.py \
  --case start_does_not_select_arrival --config outputs/candidate.json
```

退出码 `0` 表示配置符合该用例，`1` 表示不符合，`2` 表示调用或文件错误。人工复核执行记录中是否先检查轨迹、无多余默认值追问、实际生成了要求的文件且读取核对摘要，并记录模型版本、语言和结果。检查器离线运行，不调用 AI，也不验证执行记录或实际文件；单元测试只证明检查器能识别正确和错误配置，不代表自然语言评测已经通过。日常使用 Skill 无需读取评测材料。

## 模型与参考资料

模型参考耐力学社 / Pili（表哥）的[《耐力科学|体感一致配速表全面指南》](https://mp.weixin.qq.com/s/spYCP-upbqAZN0kzUm-0ng)，采用独立实现的等效距离与疲劳曲线，不代表 RunArt.Net 的官方输出。结果依赖轨迹海拔和平滑参数，参考水量用于比较赛段差异；示例目标不代表个人能力评估。

文章及配图保存在 [docs/reference/](docs/reference/)，仅作为背景资料，保留原文来源与版权声明；使用 Skill 无需读取这些资料。
