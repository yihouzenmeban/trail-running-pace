# 耐力学社体感一致配速表 Skills

[简体中文](README.md) | [English](README.en.md)

基于耐力学社体感一致配速思路的社区独立实现，将 GPX 或 KML 比赛轨迹转换成按检查点（CP）分段的越野跑配速表，同时比较多组目标完赛时间。可通过 AI 助手调用 `even-effort-pace-chart`，也可直接使用命令行。

> **来源与版权说明**：思路参考耐力学社 / Pili（表哥）的[《耐力科学|体感一致配速表全面指南》](https://mp.weixin.qq.com/s/spYCP-upbqAZN0kzUm-0ng)。本项目独立实现等效距离与疲劳曲线，并非 RunArt.Net 官方工具或输出。原文及配图的权利归原权利人所有；[仓库归档](docs/reference/)保留来源与版权声明，第三方资料的使用条件以原文声明为准。

- 优先读取轨迹内的 CP；缺少可用站点时再提供人工 CP 列表。
- 单个目标默认展开五组方案，相邻间隔 30 分钟；支持自定义间隔或目标列表。
- 展示分段距离、爬升、下降、坡度分布、海拔剖面和下一段参考水量。
- 支持站点停留和关门时间；未提供关门时间时，位置列不显示关门信息。
- 默认仅导出 SVG，括号内显示区间配速；可选等强配速、到达钟点及其他导出格式。

## 环境要求

- **运行**：Python 3.10 或更高版本，仅使用标准库，无需额外 Python 依赖或在线服务。
- **快捷安装**：使用下方安装器时，需要 Node.js、npm 和 Git；也可手动复制安装。
- **轨迹**：本地 GPX 或 KML 文件，轨迹点需要包含坐标和海拔。

## 安装与使用 Skills

### 快速安装

在需要使用 Skills 的项目目录执行：

```bash
npx skills add yihouzenmeban/trail-running-pace --skill even-effort-pace-chart
```

按提示选择 AI 助手。不加 `-g` 时安装到当前项目；添加 `-g` 可安装到用户级技能目录，供多个项目使用：

```bash
npx skills add yihouzenmeban/trail-running-pace --skill even-effort-pace-chart -g
```

手动安装时，将 `skills/even-effort-pace-chart/` 整个目录复制到所用 AI 助手的技能目录。运行时不依赖仓库中的示例或参考文章。

### 首次使用

将 `race.gpx` 替换为自己的 GPX 或 KML 轨迹路径，向 AI 助手提供目标时间。在支持 `$名称` 调用的助手中，可以使用：

```text
$even-effort-pace-chart
用 race.gpx 生成体感一致配速表，
目标完赛时间 14 小时，相邻方案间隔 30 分钟，出发时间早上六点，输出到 output/my-race/。
```

也可以在自然语言请求中指定使用 `even-effort-pace-chart`。助手会先检查轨迹和 CP，再生成配速表。上述请求默认只输出 SVG，括号内为区间配速；提供出发时间不会切换为到达钟点。图表标签默认为中文。

## 效果预览与示例

![天地留白100K 配速表示例](examples/tiandi-liubai-100k/pace-chart.svg)

| 示例 | 轨迹 | 配置 | 配速表 |
| --- | --- | --- | --- |
| 天地留白 100K | [GPX](examples/tiandi-liubai-100k/天地留白100K.gpx) | [12–16 小时方案](examples/tiandi-liubai-100k/config.json) | [SVG](examples/tiandi-liubai-100k/pace-chart.svg) |
| 大境门 DGW100K | [KML](examples/大境门/2026京东大境门古长城越野赛by%20UTMB®DGW100K.kml) | [24 小时中心目标](examples/大境门/config.json) | [SVG](examples/大境门/pace-chart.svg) |

两个示例目录均保留原始轨迹、配置和四种导出结果。示例配置显式选择全部四种格式，不代表默认输出；其中的目标时间也不代表个人能力评估。

## 命令行快速开始

以下命令在克隆后的仓库根目录执行。先检查示例轨迹和 CP，再使用示例配置生成 12、13、14、15、16 小时五组方案：

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py inspect \
  'examples/tiandi-liubai-100k/天地留白100K.gpx'

python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  'examples/tiandi-liubai-100k/天地留白100K.gpx' \
  --config examples/tiandi-liubai-100k/config.json \
  --output-dir output/tiandi-liubai-100k
```

结果写入已被 Git 忽略的 `output/`。需要替换已有结果时添加 `--overwrite`。

KML 示例见上表。对于未声明高度模式或采用 `clampToGround` 的文件，需要先确认坐标高度可用于计算，再显式启用 `use_kml_altitudes`；完整规则和检查命令见[配置文档的 KML 输入说明](skills/even-effort-pace-chart/references/configuration.md#kml-输入)。

## 配置与输出

通过 AI 助手使用时，直接说明自己的需求即可。命令行用户可将以下内容保存为 `race.json`：

```json
{
  "name": "我的比赛",
  "target": "14:00"
}
```

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  race.gpx --config race.json --output-dir output/my-race
```

这份最小配置生成 13:00、13:30、14:00、14:30、15:00 五组方案，默认早上六点发枪，输出 SVG。

| 常用参数 | 默认值 | 说明 |
| --- | --- | --- |
| `target` / `targets` | 必须提供其一 | 中心目标或明确的目标列表，时长支持 `H:MM`、`H:MM:SS`，可超过 24 小时 |
| `target_step_minutes` | `30` | 单个目标展开五组时的相邻间隔，单位分钟 |
| `start_time` | `"06:00"` | 本地发枪时间，可填 `HH:MM` 或完整日期时间 |
| `secondary_display` | `"pace"` | 括号内显示区间配速、等强配速或到达钟点 |
| `output_formats` | `["svg"]` | 选择导出格式，可组合使用 |

括号内的三种模式分别为 `"pace"`、`"equivalent_pace"`、`"arrival_time"`。出发时间与括号内容独立。可选参数按“当前明确要求 > 指定使用的配置 > 脚本默认值”处理，不从示例继承；完整字段及 CP、停留、关门时间配置见[配置文档](skills/even-effort-pace-chart/references/configuration.md)。

### 导出格式

| 格式 | 文件名 | 用途 |
| --- | --- | --- |
| SVG（默认） | `pace-chart.svg` | 独立矢量表，适合预览、缩放和分享 |
| HTML | `pace-chart.html` | 浏览器离线查看，支持横向打印 |
| CSV | `pace-chart.csv` | 在表格软件中处理各 CP、各目标的时间数据 |
| JSON | `pace-chart.json` | 保留完整计算精度、参数、来源和告警 |

如需全部四种格式，在配置中显式加入：

```json
{
  "output_formats": ["svg", "html", "csv", "json"]
}
```

## 开发与测试

```bash
python3 -m unittest discover -s skills/even-effort-pace-chart/tests -v
```

测试覆盖合成 GPX/KML 和两个真实赛道；独立复制 Skills、未携带 `examples/` 时，真实赛道测试会跳过。自然语言用例、检查器使用方式和人工复核步骤见[行为评测指南](skills/even-effort-pace-chart/evals/guide.md)。

## 模型与限制

计算公式、海拔平滑及假设见[模型文档](skills/even-effort-pace-chart/references/model.md)。结果依赖轨迹海拔和平滑参数，不保证复现赛事或其他平台的统计。参考水量用于比较赛段差异，不能据此评估个人补水需求或完赛能力。
