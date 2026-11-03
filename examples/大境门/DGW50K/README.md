# 大境门 MGW50K 示例

[简体中文](README.md) | [English](README.en.md) | [项目首页](../../../README.md)

目录沿用 `DGW50K` 名称，轨迹与图表保留赛事组别 `MGW50K`。公开文件可复现两份配速表；三方合并对比图为人工整理的历史参考图。

## 输入与海拔修复

[原始 GPX](2026京东大境门古长城越野赛by%20UTMB®MGW50K.gpx) 有 59 点缺少海拔，生成配速表时使用下面的补全副本。缺失分为两段，已知端点之间分别约 834.6 m、34.1 m。

[MGW50K-elevation-filled.gpx](MGW50K-elevation-filled.gpx) 是沿水平距离在已知端点之间线性插值的副本。[elevation-repair.json](elevation-repair.json) 记录点索引、缺失范围、补全方法及两份文件的哈希。副本已完成海拔补全；插值不能还原缺失区间的小坡。

## 配速表与复现

| 配置 | 方案 | 结果 |
| --- | --- | --- |
| [config.json](config.json) | 5–12.5 小时，每隔 30 分钟，共 16 组 | [pace-chart.svg](pace-chart.svg) |
| [config-6h15m.json](config-6h15m.json) | 仅 6 小时 15 分钟 | [pace-chart-6h15m.svg](pace-chart-6h15m.svg) |

两份配置均使用默认的 SVG、06:00 出发和括号内区间配速，并明确选择本轨迹的 CP ID。

需要 Python 3.10+，在仓库根目录执行：

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py inspect \
  'examples/大境门/DGW50K/MGW50K-elevation-filled.gpx'

python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  'examples/大境门/DGW50K/MGW50K-elevation-filled.gpx' \
  --config 'examples/大境门/DGW50K/config.json' \
  --output-dir output/dgw50k

python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  'examples/大境门/DGW50K/MGW50K-elevation-filled.gpx' \
  --config 'examples/大境门/DGW50K/config-6h15m.json' \
  --output-dir output/dgw50k-6h15m
```

输出写入被 Git 忽略的 `output/`，替换已有结果时加 `--overwrite`。

## 三方历史参考图

[runart-comparison.svg](runart-comparison.svg) 包含耐力学社 / RunArt.Net 配速表截图中的数据、本仓库方案、佳明 2026-09-12 大境门活动，依次展示：

1. 16 档方案的各站累计时间对照。
2. 三方累计距离、分段爬升与下降；学社和仓库数值旁附各自减去佳明的差值。
3. 仓库 6:15 方案与佳明实际的逐站时间对照，时间差为实际减去方案，负值表示提前。

图中的经过时间包含停留，中间站地形由 FIT 逐圈数据按距离插值，再由相邻累计值相减估算；终点采用平台汇总，先相减再取整。个人原始 FIT 未公开。

三方合并图仅提供 SVG；用自己的 FIT 生成方案与实际活动的对照图，见[活动对比文档](../../../skills/even-effort-pace-chart/references/comparison.md)。
