# 大境门 DGW100K 示例

[简体中文](README.md) | [English](README.en.md) | [项目首页](../../../README.md)

本示例使用用户提供的比赛 KML 副本，可用公开轨迹与配置重新生成配速表。

## 输入与结果

| 文件 | 内容 |
| --- | --- |
| [比赛 KML](2026京东大境门古长城越野赛by%20UTMB®DGW100K.kml) | 原始路线与站点候选 |
| [config.json](config.json) | 10–24 小时、每隔 1 小时，共 15 组；06:00 出发；显式选用 CP 和 KML 坐标高度 |
| [pace-chart.svg](pace-chart.svg) | 括号内为区间配速；同配置另导出 HTML、CSV、JSON |

配置中的 `cp_selection` 是对本文件候选站点的明确选择，不是其他轨迹的默认值。若换用重新导出的 KML，应再次检查候选 ID。

## 复现

需要 Python 3.10+，在仓库根目录执行：

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py inspect \
  'examples/大境门/DGW100K/2026京东大境门古长城越野赛by UTMB®DGW100K.kml' \
  --use-kml-altitudes

python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  'examples/大境门/DGW100K/2026京东大境门古长城越野赛by UTMB®DGW100K.kml' \
  --config 'examples/大境门/DGW100K/config.json' \
  --output-dir output/dgw100k
```

本示例显式采用文件内提供的高度，因此检查命令带 `--use-kml-altitudes`，生成配置带 `use_kml_altitudes: true`。该选择不证明高度来自实测；其他 KML 需先核实高度含义，不能照抄开关。完整规则见[KML 输入](../../../skills/even-effort-pace-chart/references/configuration.md#kml-输入)。

生成四种格式到被 Git 忽略的 `output/dgw100k/`，替换已有结果时加 `--overwrite`。本目录没有实际活动对比；历史爬升算法数值比较见[爬升方案](../../../skills/even-effort-pace-chart/references/ascent-options.md)。复现指使用相同输入重新计算方案，不保证不同代码版本的输出逐字节一致。
