# GPX / KML 体感一致配速表 Skill

[简体中文](README.md) | [English](README.en.md)

将 GPX 或 KML 比赛轨迹转换成按 CP 分段的越野跑配速表，同时比较多组目标完赛时间。既可作为 `even-effort-pace-chart` Skill 使用，也可直接通过命令行生成。

- 默认读取轨迹内的 CP；缺少可用站点时再提供人工 CP 列表。
- 单个目标时间默认展开五组方案，相邻间隔 30 分钟；支持自定义间隔或目标列表。
- 展示分段距离、爬升、下降、坡度分布、海拔肖像和下一段参考水量。
- 支持站点停留和关门时间；未提供关门时间时，位置列不显示关门信息。
- 同时导出 HTML、SVG、CSV 和 JSON，可离线查看、打印或继续处理。

![天地留白100K 配速表示例](examples/tiandi-liubai-100k/pace-chart.svg)

## 环境要求

Python 3.10 或更高版本，仅使用标准库，无需安装额外依赖或配置在线服务。轨迹点需要包含坐标和海拔，GPX/KML 根据 XML 根元素自动识别。

## 作为 Skill 使用

将 `skills/even-effort-pace-chart/` 整个目录复制到所用代理的技能目录，保留其中的 `SKILL.md`、`agents/`、`scripts/` 和 `references/`，然后在对话中调用：

```text
$even-effort-pace-chart
用 examples/tiandi-liubai-100k/天地留白100K.gpx 生成体感一致配速表，
目标完赛时间 14 小时，相邻方案间隔 30 分钟，输出到 output/my-race/。
```

Skill 会先检查轨迹和 CP，再根据目标时间及配置生成结果。也可以提供 KML、自定义目标列表、各站停留时间和关门时间。图表标签默认为中文。

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

完整示例保存在 `examples/tiandi-liubai-100k/`，包含 GPX、配置和四种导出结果；轨迹约 101.25 km，当前默认参数下累计爬升约 5,332 m。

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
| `start_time` | 不展示 | 发枪日期时间，仅用于标注；表中仍显示比赛经过时长 |
| `pace_basis` | `"distance"` | 括号内默认显示实际距离配速，可设为 `"equivalent"` 显示等效配速 |
| `sample_m` | `5` | 沿距离插值的间隔，单位米 |
| `smoothing_m` | `20` | 海拔肖像与坡度分布的居中平滑窗口全宽，单位米 |
| `ascent_smoothing_m` | `100` | 累计爬升、下降的独立统计窗口全宽，单位米 |
| `use_kml_altitudes` | `false` | 显式采用未声明高度模式或 clampToGround 的 KML 坐标高度 |
| `checkpoint_overrides` | 不覆盖 | 按候选点 ID 设置名称、停留分钟数 `rest_minutes`、关门时长 `cutoff` 等 |
| `checkpoints` | 从轨迹读取 | 没有可用内嵌 CP 时，手动提供名称和累计公里数 |

目标完赛时间包含站点停留。关门时间按发枪后经过时长填写；环线、折返或偏离轨迹的 CP 可能需要明确确认位置。

完整字段、人工 CP 和关门时间示例见[配置文档](skills/even-effort-pace-chart/references/configuration.md)，计算公式与平滑方案见[模型文档](skills/even-effort-pace-chart/references/model.md)。

## 开发与测试

```bash
python3 -m unittest discover -s skills/even-effort-pace-chart/tests -v
```

完整仓库会执行 GPX/KML 合成轨迹测试，以及天地留白 100K 和大境门 KML 真实赛道回归测试；单独复制 Skill、未携带 examples 时，真实赛道测试会跳过。

## 模型与参考资料

模型参考耐力学社 / Pili（表哥）的[《耐力科学|体感一致配速表全面指南》](https://mp.weixin.qq.com/s/spYCP-upbqAZN0kzUm-0ng)，采用独立实现的等效距离与疲劳曲线，不代表 RunArt.Net 的官方输出。结果依赖轨迹海拔和平滑参数，参考水量用于比较赛段差异；示例目标不代表个人能力评估。

文章及配图保存在 [docs/reference/](docs/reference/)，仅作为背景资料，保留原文来源与版权声明；使用 Skill 无需读取这些资料。
