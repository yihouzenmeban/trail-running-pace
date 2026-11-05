# 大境门 DGW100K：15 小时配速方案

以 15 小时为中心，展示 14:00、14:30、15:00、15:30、16:00 五档完赛时间。区间配速显示在括号内；累计时间从发枪开始计算，默认未计入站内停留，也未校核关门时间。

- `pace-chart.html`：逐站填写**本站出发到下一站的携水总量**，单位为毫升。填写后点击“下载填写版 HTML”保存，或直接打印；原文件不会自动保存填写内容。
- `pace-chart.svg`：携水量留白，适合打印后手写；填写 HTML 不会改变 SVG。
- `config.json`：目标、站点选择及手动携水设置。

里程来自 KML 轨迹，未按站名中的公里数缩放。高度采用 KML 坐标值，未做地形或垂直基准校正。图表默认显示 06:00 发枪，仅为工具默认值，并非已确认的赛事时间。携水前请核实各站供水、容器容量和个人需求。

在仓库根目录重新生成：

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  'examples/大境门/DGW100K/2026京东大境门古长城越野赛by UTMB®DGW100K.kml' \
  --config 'examples/大境门/DGW100K/15h/config.json' \
  --output-dir 'examples/大境门/DGW100K/15h' --overwrite
```
