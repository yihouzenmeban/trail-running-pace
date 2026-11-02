# 耐力学社体感一致配速表 Skills

[简体中文](README.md) | [English](README.en.md)

基于耐力学社体感一致配速思路的社区独立实现，将 GPX、KML 比赛轨迹或实际 FIT 路线转换成按检查点（CP）分段的越野跑配速表，同时比较多组目标完赛时间。可通过 AI 助手调用 `even-effort-pace-chart`，也可直接使用命令行。

> **来源与版权说明**：思路参考耐力学社 / Pili（表哥）的[《耐力科学|体感一致配速表全面指南》](https://mp.weixin.qq.com/s/spYCP-upbqAZN0kzUm-0ng)。本项目独立实现等效距离与疲劳曲线，并非 RunArt.Net 官方工具或输出。原文及配图的权利归原权利人所有；[仓库归档](docs/reference/)保留来源与版权声明，第三方资料的使用条件以原文声明为准。

- 优先读取轨迹内的 CP；缺少可用站点时再提供人工 CP 列表。
- 单个目标默认展开五组方案，相邻间隔 30 分钟；支持自定义间隔或目标列表。
- 展示分段距离、爬升、下降、坡度分布、海拔剖面和下一段参考水量。
- 支持站点停留和关门时间；未提供关门时间时，位置列不显示关门信息。
- 默认仅导出 SVG，括号内显示区间配速；可选等强配速、到达钟点及其他导出格式。
- 可将实际 FIT 活动与目标方案对照，比较各站经过时间、相邻站耗时和地形数据。

## 环境要求

- **运行**：Python 3.10 或更高版本，GPX/KML 配速表仅使用标准库；FIT 路线及实际活动对比需安装可选 FIT 依赖。
- **快捷安装**：使用下方安装器时，需要 Node.js、npm 和 Git；也可手动复制安装。
- **轨迹**：本地 GPX、KML、FIT 或单活动 FIT ZIP，轨迹点需要包含坐标和海拔；FIT 路线使用设备记录距离及人工 CP。

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

| 示例 | 轨迹 | 配置 | 配速表 | 对比图 |
| --- | --- | --- | --- | --- |
| 天地留白 100K | [GPX](examples/tiandi-liubai-100k/天地留白100K.gpx) | [12–16 小时方案](examples/tiandi-liubai-100k/config.json) | [SVG](examples/tiandi-liubai-100k/pace-chart.svg) | [佳明实际 / 仓库 15、16、17 小时](examples/tiandi-liubai-100k/garmin-comparison.svg) |
| 天地留白 100K · 实际路线 | 本地 FIT（不随仓库公开） | [15、16、17 小时方案](examples/tiandi-liubai-100k/config-fit.json) | [基于 FIT 的 SVG](examples/tiandi-liubai-100k/pace-chart-fit.svg) | [佳明实际 / FIT 路线方案](examples/tiandi-liubai-100k/garmin-comparison2.svg) |
| 大境门 DGW100K | [KML](examples/大境门/DGW100K/2026京东大境门古长城越野赛by%20UTMB®DGW100K.kml) | [10–24 小时，每隔 1 小时](examples/大境门/DGW100K/config.json) | [SVG](examples/大境门/DGW100K/pace-chart.svg) | — |
| 大境门 MGW50K | [原始 GPX](examples/大境门/DGW50K/2026京东大境门古长城越野赛by%20UTMB®MGW50K.gpx) / [海拔补全副本](examples/大境门/DGW50K/MGW50K-elevation-filled.gpx) | [5–12.5 小时，每隔 30 分钟](examples/大境门/DGW50K/config.json) | [SVG](examples/大境门/DGW50K/pace-chart.svg) | [耐力学社 / 仓库 / 佳明对比](examples/大境门/DGW50K/runart-comparison.svg) |

原有两个 GPX/KML 100K 示例显式选择四种导出格式；FIT 路线和 50K 示例使用默认的 SVG、06:00 出发及括号内区间配速。示例目标不代表个人能力评估。50K 目录按 `DGW50K` 命名，图表保留赛事组别名称 `MGW50K`。

50K 原始 GPX 缺失 59 点海拔，分两段，已知端点之间分别约 834.6 m、34.1 m。生成配速表时使用沿距离线性插值的副本和同目录配置；原文件不变，[补全记录](examples/大境门/DGW50K/elevation-repair.json)保留缺失范围和校验值。

50K 另提供单列 [6 小时 15 分钟方案](examples/大境门/DGW50K/pace-chart-6h15m.svg)及其[配置](examples/大境门/DGW50K/config-6h15m.json)，沿用默认的 06:00 出发和括号内区间配速。

天地留白对比图仅包含佳明实际与仓库方案，分为「时间表现」和「赛道数据对比」。15、16、17 小时方案各有上方累计差距曲线、下方区间快慢柱图；绿色表示实际领先／本段快，红色表示落后／本段慢。图下耗时表以 CP 为行、实际与各方案为列，首列合并站名与累计里程。实际列只显示本段耗时，预计列加粗显示「本段耗时（实际 − 预计差额）」，保留到秒；佳明实际更慢标红，否则标绿（含持平），实际列保持中性色。地形保留全程汇总卡、分段爬升与下降分组柱图。佳明使用 2026-10-31「2026 徽州古城秋季赛」活动，经过时间包含停留，全程为 16:46:04；原有 12–16 小时配置和配速表保持不变。

新增的 `garmin-comparison2.svg` 改用这次活动的 FIT 记录距离与海拔生成方案，保留同一组已核对的 CP 经过时刻。路线为 101.877 km，现有算法重算爬升 / 下降约 4783 / 4760 m；佳明实际侧仍为平台的 5019 / 5023 m。它用于按实际路线复盘配速分配，与原 GPX 版本并存，不强行对齐地形总量。原始活动保存在本地被忽略的 `output/`。

大境门合并对比图依次展示 16 档方案时间、三方地形数据，以及佳明实际活动与仓库 6:15 方案的时间对照。耐力学社数据来自用户提供的截图；佳明使用 2026-09-12 的大境门活动，时间包含停留。实际活动对照按秒显示，差值为佳明实际减去方案，负值表示提前。

对比 SVG 仅作参考，CP 经过时间按实际轨迹投影估算，非官方打卡。距离为累计距离；佳明分段爬升、下降由 FIT 逐圈距离插值估算的相邻站累计值相减得到，终点使用平台原值，差值先用原值计算再取整。天地留白逐圈合计爬升 / 下降为 5018 / 5024 m，平台为 5019 / 5023 m，未按比例调整。

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

## 完赛活动对比

可向 AI 助手说明：“用这条 FIT 活动与比赛配置对比，参照目标为 15、16、17 小时，包含每两个站之间的耗时”。安装可选依赖后，可直接离线生成：

```bash
python3 -m pip install -r skills/even-effort-pace-chart/scripts/requirements-comparison.txt

python3 skills/even-effort-pace-chart/scripts/compare_activity.py generate race.gpx \
  --config race.json --fit activity-original.zip --summary activity-details.json \
  --targets 15:00 16:00 17:00 --output-dir output/comparison
```

支持原始 FIT 或 FIT ZIP，省略 `--summary` 时使用 FIT session 汇总。默认仅导出包含时间表现和赛道数据对比的 SVG；可加 `--export-json`。`--targets` 精确覆盖目标列表，不修改比赛配置；分段时间包含途中停留。每个目标用累计差距曲线和下方区间快慢柱图配对展示，图下按 CP 列出实际本段耗时及「预计本段耗时（实际 − 预计差额）」，站名与累计里程合为首列。地形用全程汇总卡和爬升、下降分组柱图。独立打开 SVG 可悬停或聚焦查看累计经过时间、完整站名、双方累计距离及地形差值。

若要按实际 FIT 重新生成路线方案，可将上述首个 `race.gpx` 换成 FIT／FIT ZIP，并提供以设备累计距离定位的 CP 配置；配速表生成也支持同一输入。距离保留设备记录值，爬升沿用现有算法独立重算，详见[配置文档的 FIT 输入说明](skills/even-effort-pace-chart/references/configuration.md#fit-作为路线输入)。

需要从佳明读取时，将 `GARMIN_PERSONAL_API_KEY` 放在环境变量或本地被忽略的 `.env.local` 中，再执行：

```bash
python3 skills/even-effort-pace-chart/scripts/compare_activity.py list \
  --start-date 2026-10-01 --end-date 2026-11-02 --env-file .env.local

python3 skills/even-effort-pace-chart/scripts/compare_activity.py fetch <activity-id> \
  --env-file .env.local
```

下载默认写入 `output/activities/<activity-id>/`，离线 `inspect`/`generate` 不访问网络。完整参数、CP 歧义处理及指标限制见[活动对比文档](skills/even-effort-pace-chart/references/comparison.md)。

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

测试覆盖合成 GPX/KML、FIT 记录处理及真实赛道；独立复制 Skills、未携带 `examples/` 时，包内真实赛道测试会跳过。自然语言用例、检查器使用方式和人工复核步骤见[行为评测指南](skills/even-effort-pace-chart/evals/guide.md)。

## 模型与限制

爬升默认不做窗口平滑（`ascent_smoothing_m: 0`），直接在清理后的原始海拔顶点上采用 10 米峰谷反转阈值；显示曲线独立使用 5 米采样、20 米平滑。显式设置正数 `ascent_smoothing_m` 可启用爬升平滑。孤立海拔尖峰修正会报告改动，水平简化需显式开启。`inspect` 和生成摘要均提供输入质量与处理前后对比。旧的 100 米窗口统计可显式选择，迁移方式见[配置文档](skills/even-effort-pace-chart/references/configuration.md#旧窗口口径与显式过滤)。

方案对比、默认选择依据及切换方式见[爬升算法方案](skills/even-effort-pace-chart/references/ascent-options.md)；计算公式、过滤规则及假设见[模型文档](skills/even-effort-pace-chart/references/model.md)。结果依赖轨迹海拔、算法和阈值，不保证复现赛事或其他平台的统计。参考水量用于比较赛段差异，不能据此评估个人补水需求或完赛能力。
