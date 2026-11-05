# 大境门 DGW100K：15 小时配速方案

[简体中文](README.md) | [English](README.en.md) | [DGW100K 示例](../README.md)

以 15 小时为中心，展示 14:00、14:30、15:00、15:30、16:00 五档完赛时间。区间配速显示在括号内；累计时间从发枪开始计算，默认未计入站内停留，也未校核关门时间。

- [pace-chart.html](pace-chart.html)：适合浏览和打印的配速表。
- [pace-chart.svg](pace-chart.svg)：可独立查看的配速表。
- [config.json](config.json)：目标、站点选择和导出格式。

水量使用默认距离模式，按每 10 等效公里 700 毫升比较各段需求，并非个人饮水建议。里程来自 KML 轨迹，未按站名中的公里数缩放。高度采用 KML 坐标值，未做地形或垂直基准校正。图表默认显示 06:00 发枪，仅为工具默认值，并非已确认的赛事时间。携水前请核实各站供水、容器容量和个人需求。

在仓库根目录重新生成：

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  'examples/大境门/DGW100K/2026京东大境门古长城越野赛by UTMB®DGW100K.kml' \
  --config 'examples/大境门/DGW100K/15h/config.json' \
  --output-dir output/dgw100k-15h
```

结果写入 Git 忽略的 `output/dgw100k-15h/`；需要替换已有结果时再加 `--overwrite`。
