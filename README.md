# Pace

跑步、越野跑与配速相关资料。

## GPX 体感一致配速表 Skill

`skills/even-effort-pace-chart/` 提供可独立复制使用的 Skill，以及只依赖 Python 3.10+ 标准库的命令行工具。根据下方归档文章的思路独立实现，默认读取 GPX 内的 CP，生成 HTML、SVG、CSV 和 JSON；不依赖 RunArt.Net 服务。

- 默认沿距离每 **5 米插值**，采用 **20 米居中窗口**平滑海拔，两个参数均可调整。
- 默认生成目标时间前后共五列，相邻间隔半小时；支持自定义间隔或明确指定一组目标时间。
- 支持 CP 停留、历经关门时间、分段海拔肖像和坡度分布。环线、折返线 CP 投影存在歧义时需要明确指定位置。
- 缺少可用的 GPX CP 时再补充人工站点；共用起终点会自动展开为两行。

先检查轨迹和 CP：

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py inspect 'assets/天地留白100K.gpx'
```

创建配置文件（24 小时仅为演示目标，不代表能力或完赛建议）：

```bash
cat > /tmp/pace-race.json <<'JSON'
{
  "name": "天地留白100K · 演示",
  "target": "24:00"
}
JSON

python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  'assets/天地留白100K.gpx' \
  --config /tmp/pace-race.json \
  --output-dir /tmp/pace-race-output
```

将输入路径替换为自己的 GPX 即可；示例轨迹为用户提供的本地测试数据，不是运行工具的必要依赖。上面的配置输出 23:00、23:30、24:00、24:30、25:00 五列。若只需要自定义目标列表，使用 `"targets": ["22:30", "24:00", "27:15"]` 替换 `target`。

输出目录中的 `pace-chart.html` 可离线打开、横向打印；`pace-chart.svg` 是包含文字和图形的独立矢量表；CSV 便于表格软件处理；JSON 保留参数、原始精度和输入校验摘要。

技能入口为 `skills/even-effort-pace-chart/SKILL.md`，详细配置和算法分别见同目录的 `references/configuration.md`、`references/model.md`。使用支持 Skill 的代理时，可自行复制整个技能目录到相应技能位置，再调用 `$even-effort-pace-chart`。本仓库不自动安装或创建全局链接。

验证：

```bash
python3 -m unittest discover -s skills/even-effort-pace-chart/tests -v
```

合成轨迹测试不依赖外部数据；本地存在 `assets/天地留白100K.gpx` 时还会执行真实赛道回归测试。模型没有复现 RunArt.Net 的未公开实现，缺失关门时间时不会声称已完成校核；参考水量只用于比较赛段差异。

## 已归档文章

- `耐力科学_体感一致配速表全面指南.md`：由用户提供的 18 页 PDF 整理，保留原文正文、图示、作者介绍和版权声明。
- `assets/pace-chart/`：文章引用的 17 张图片，包括配速表示例、掉速曲线、跑力包线和比赛完成时间对照表。

原文标题：耐力科学|体感一致配速表全面指南。发布账号：耐力學社。原文注明文章来源于隆景体育，作者耐力学社。发布时间：2025 年 8 月 26 日 07:27（中国香港）。

原文链接：https://mp.weixin.qq.com/s/spYCP-upbqAZN0kzUm-0ng

## PDF 整理方式

本次使用全局安装的 OpenDataLoader PDF 2.5.16，在本地导出 Markdown、JSON 和独立图片：

```bash
opendataloader-pdf \
  --format markdown,json \
  --image-output external \
  --output-dir /tmp/pace-opendataloader \
  '/Users/yihouzenmeban/Downloads/耐力科学_体感一致配速表全面指南.pdf'
```

解析后核对 PDF 页面，统一中文兼容字和标题层级，修复断词、跨页断句及丢失的连字符，将图片引用调整为仓库内的相对路径。原始 JSON 和临时预览保留在仓库外。

## 来源与版权

本仓库的文章是对用户提供资料的格式整理。原文关于知识方案、制表工具及生成配速表的不同版权说明，完整保留在文章的“五、版权声明”中；整理不改变这些声明。
