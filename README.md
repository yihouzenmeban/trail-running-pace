# 体感一致配速表 Skills

[简体中文](README.md) | [English](README.en.md)

基于耐力学社体感一致配速思路的社区独立实现。赛前，将 GPX、KML 或 FIT 路线转换成按检查点（CP）分段的多目标配速表；赛后，将 FIT 活动与方案对照，查看累计差距、相邻站耗时和地形差异。可通过 AI 助手调用 `even-effort-pace-chart`，也可直接使用命令行。

思路参考耐力学社 / Pili（表哥）的[《耐力科学｜体感一致配速表全面指南》](https://mp.weixin.qq.com/s/spYCP-upbqAZN0kzUm-0ng)。本项目独立实现等效距离与疲劳曲线，并非 RunArt.Net 官方工具或输出；详见[来源与版权](#来源与版权)。

## 效果预览

![徽州古城100K 配速表示例](examples/huizhou-gucheng-100k/pace-chart.svg)

| 示例与说明 | 配速表 | 活动对比 |
| --- | --- | --- |
| [徽州古城 100K](examples/huizhou-gucheng-100k/README.md)：GPX 制表与 FIT 赛后复盘 | [GPX 方案](examples/huizhou-gucheng-100k/pace-chart.svg) / [FIT 路线方案](examples/huizhou-gucheng-100k/pace-chart-fit.svg) | [按赛前 GPX](examples/huizhou-gucheng-100k/garmin-comparison.svg) / [按实际 FIT](examples/huizhou-gucheng-100k/garmin-comparison2.svg) |
| [大境门 DGW100K](examples/大境门/DGW100K/README.md)：公开 KML 可复现 | [10–24 小时](examples/大境门/DGW100K/pace-chart.svg) / [15 小时方案](examples/大境门/DGW100K/15h/README.md) | — |
| [大境门 MGW50K](examples/大境门/DGW50K/README.md)：使用公开的海拔补全副本生成配速表，含赛前 GPX 与实际 FIT 两版赛后对比 | [5–12.5 小时](examples/大境门/DGW50K/pace-chart.svg) / [6:15 单列](examples/大境门/DGW50K/pace-chart-6h15m.svg) / [FIT 路线方案](examples/大境门/DGW50K/pace-chart-fit.svg) | [按赛前 GPX](examples/大境门/DGW50K/garmin-comparison.svg) / [按实际 FIT](examples/大境门/DGW50K/garmin-comparison2.svg) |

各示例说明包含输入来源、配置、复现所需文件、命令和结果口径。

## 安装与使用

所有方式都需要 **Python 3.10+**。GPX/KML 配速表仅使用标准库；FIT 输入和活动对比需要[可选依赖](skills/even-effort-pace-chart/references/comparison.md#准备输入)。

有两种方式，按需选择：

- **在 AI 助手中使用**：先安装 Skill，再用自然语言调用。适合让助手检查路线、处理歧义并生成图表。
- **直接使用命令行**：不需要安装 Skill，克隆仓库后运行脚本；见[命令行使用](#命令行使用)。

### 在 AI 助手中使用

#### 安装 Skill（任选一种）

1. **npx（推荐）**：需要 Node.js、npm 和 Git。在项目目录执行：

   ```bash
   npx skills add yihouzenmeban/trail-running-pace --skill even-effort-pace-chart
   ```

   按提示选择 AI 助手。默认安装到当前项目；加 `-g` 安装到用户级技能目录，此时可在任意目录执行。

2. **手动安装**：不需要 Node.js。从 [GitHub Releases](https://github.com/yihouzenmeban/trail-running-pace/releases) 下载带版本号的 ZIP，解压后得到 `even-effort-pace-chart/`；如果已克隆仓库，也可以直接复制 `skills/even-effort-pace-chart/`。将 `even-effort-pace-chart/` 整个目录放入助手的技能目录即可。技能目录已包含运行所需文件，不依赖仓库示例或来源文章。

3. **WorkBuddy**：如果你使用 WorkBuddy，用分享页安装，不需要执行上面的 npx 或手动复制：

   1. 打开 [WorkBuddy 技能分享页](https://www.workbuddy.cn/share/asset?shareCode=VxFVK8iJONQ7o2r3K9ffpU&sig=q3nO3wLULv--gGj0)，按提示在 WorkBuddy 客户端安装。
   2. 在「专家·技能·连接器 → 技能 → 已安装」中确认该技能已启用。

4. **ClawHub**：如果你使用 OpenClaw，用 ClawHub CLI 安装，需要 Node.js：

   ```bash
   npx -y clawhub install @yihouzenmeban/even-effort-pace-chart
   ```

   装到 `skills/@yihouzenmeban/even-effort-pace-chart/`，内容完整（脚本、参考文档都在里面）。也可以在 [ClawHub 页面](https://clawhub.ai/yihouzenmeban/skills/even-effort-pace-chart)查看。

#### 首次使用

安装完成后，准备一份 GPX、KML 或 FIT 轨迹（也可以先用[公开示例](examples/huizhou-gucheng-100k/README.md)），向助手提供轨迹路径和目标时间。

- **Claude Code**：用斜杠命令调用：

  ```text
  /even-effort-pace-chart
  用 race.gpx 生成体感一致配速表，目标完赛时间 14 小时，输出到 output/my-race/。
  ```

- **其他助手**：在支持 `$名称` 调用的助手中用 `$even-effort-pace-chart`；也可以在自然语言请求中直接指定 `even-effort-pace-chart`，让助手自行加载。

默认行为：

- 以目标时间为中心，向前、向后各展开两档，共五组方案，相邻间隔 30 分钟。例如目标 14:00 生成 13:00、13:30、14:00、14:30、15:00 五组完赛目标；这些是完赛用时，不是钟点。
- 默认 06:00 发枪。指定出发时间只影响钟点换算，不会把括号内容从区间配速改为到达钟点。
- 仅输出 SVG，括号内显示刚完成区间的配速，图表标签为中文。
- 优先使用轨迹内可识别的 CP；内嵌 CP 缺失或不可用时，改用人工 CP 列表（不能与内嵌 CP 混用）；FIT 路线必须使用人工 CP。

默认水量按等效距离计算，仅供赛段比较，并非个人饮水建议。需要结合天气和个人情况规划携水时，直接告诉助手；它会按需询问比赛日期与出发时间、饮水经验、携水容量和站点供水情况，确认个人饮水速率后按赛段耗时计算。天气只用于辅助确认速率，程序不会自动调整。详见[携水与天气](skills/even-effort-pace-chart/references/configuration.md#按耗时规划携水)。

### 命令行使用

不需要安装 Skill。先克隆仓库：

```bash
git clone https://github.com/yihouzenmeban/trail-running-pace.git
cd trail-running-pace
```

以下命令在仓库根目录执行。将下面内容保存为 `race.json`：

```json
{
  "name": "我的比赛",
  "target": "14:00"
}
```

`target` 是完赛用时（这里为 14 小时），不是出发钟点。

先用 `inspect` 检查公开示例轨迹，再生成配速表：

```bash
python3 skills/even-effort-pace-chart/scripts/pace_chart.py inspect \
  'examples/huizhou-gucheng-100k/徽州古城100K.gpx'

python3 skills/even-effort-pace-chart/scripts/pace_chart.py generate \
  'examples/huizhou-gucheng-100k/徽州古城100K.gpx' \
  --config race.json --output-dir output/my-race
```

生成 13:00、13:30、14:00、14:30、15:00 五组完赛目标（均为完赛用时），结果为 `output/my-race/pace-chart.svg`。`output/` 已被 Git 忽略；替换已有结果时使用 `--overwrite`。

`inspect` 只输出检查结果，不写文件；`generate` 会重新读取轨迹。换成自己的轨迹时，先对该文件运行 `inspect`，处理完路线与 CP 歧义后再运行 `generate`。

两种方式共用同一套配置。配速表的所有配置项、默认值和取值说明见[完整参数表](skills/even-effort-pace-chart/references/configuration.md#参数)，包括目标、站点、爬升处理、输出格式、携水和天气。可以用自然语言向助手指定，也可以写入 `race.json`；活动对比的命令参数见[活动对比文档](skills/even-effort-pace-chart/references/comparison.md)。

## 赛后活动对比

![徽州古城 100K：16 小时方案累计差距与部分区间耗时](examples/huizhou-gucheng-100k/assets/comparison-preview.svg)

上图截取基于实际 FIT 路线的 16 小时方案；[完整对比图](examples/huizhou-gucheng-100k/garmin-comparison2.svg)包含 15、16、17 小时方案及各段爬升、下降。大境门 MGW50K 的[示例说明](examples/大境门/DGW50K/README.md#赛后活动对比)同时提供赛前 GPX 与实际 FIT 两版对比，可对照路线输入带来的差异。

有两种方式：

**在 AI 助手中使用**：向助手提供比赛轨迹、配速配置和活动 FIT，例如：

```text
用 even-effort-pace-chart 将 activity.fit 与 race.gpx、race.json 对比，
参照目标为 15、16、17 小时，包含每两个站之间的耗时，输出到 output/comparison/。
```

**使用命令行**：先安装 FIT 依赖，再离线检查并生成（以下命令在克隆后的仓库根目录执行）：

```bash
python3 -m pip install -r skills/even-effort-pace-chart/scripts/requirements-comparison.txt

python3 skills/even-effort-pace-chart/scripts/compare_activity.py inspect race.gpx \
  --config race.json --fit activity.fit \
  --targets 15:00 16:00 17:00

python3 skills/even-effort-pace-chart/scripts/compare_activity.py generate race.gpx \
  --config race.json --fit activity.fit \
  --targets 15:00 16:00 17:00 --output-dir output/comparison
```

默认输出 `garmin-comparison.svg`，支持 FIT 或单活动 FIT ZIP，无需在线凭据。`inspect` 只输出活动汇总、站点匹配和诊断信息，不写文件；CP 匹配有歧义时按提示核对后再运行 `generate`。替换已有结果时使用 `--overwrite`。读图、平台汇总、按实际 FIT 重算路线及可选佳明下载，见[活动对比文档](skills/even-effort-pace-chart/references/comparison.md)。

## 文档导航

| 需要了解什么 | 文档 |
| --- | --- |
| 配速表完整参数、默认值和取值说明 | [完整参数表](skills/even-effort-pace-chart/references/configuration.md#参数) |
| 目标列表、人工 CP、停留、关门和导出格式 | [配置与命令行](skills/even-effort-pace-chart/references/configuration.md) |
| 携水量、个人速率和天气预报 | [携水与天气](skills/even-effort-pace-chart/references/configuration.md#按耗时规划携水) |
| KML 高度、FIT 设备距离与 CP 要求 | [KML 输入](skills/even-effort-pace-chart/references/configuration.md#kml-输入) / [FIT 路线输入](skills/even-effort-pace-chart/references/configuration.md#fit-作为路线输入) |
| 活动对比、差值方向、CP 匹配和佳明读取 | [活动对比](skills/even-effort-pace-chart/references/comparison.md) |
| 等效距离、疲劳曲线、距离与海拔处理 | [模型与限制](skills/even-effort-pace-chart/references/model.md) |
| 为什么默认不平滑＋10 米阈值，如何切换 | [爬升方案与历史实验](skills/even-effort-pace-chart/references/ascent-options.md) |
| AI 助手的执行流程 | [SKILL.md](skills/even-effort-pace-chart/SKILL.md) |

爬升统计和图示平滑各自独立；结果依赖输入海拔与处理参数，可能与赛事或其他平台统计不同。

## 开发与测试

在仓库根目录分别运行技能功能测试和发布流程测试：

```bash
python3 -m unittest discover -s skills/even-effort-pace-chart/tests -v
python3 -m unittest discover -s .github/tests -v
```

技能测试覆盖路线处理、配速和活动对比。独立复制 Skills、未携带 `examples/` 时，真实赛道测试会跳过。自然语言用例及人工复核步骤见[行为评测指南](skills/even-effort-pace-chart/evals/guide.md)；开发经历见[投稿文章](docs/articles/从配速表到百公里复盘.md)。

推送涉及 `skills/even-effort-pace-chart/` 的提交到 `main` 后，[发布工作流](.github/workflows/release-skill.yml)会运行发布测试、递增补丁版本并同步两个版本字段，再向 `main` 写入版本提交、创建标签和 GitHub Release，上传仅包含技能目录的 ZIP。技能参考文档的修改也会触发该流程；继续开发前请同步自动生成的版本提交。

## 来源与版权

[参考文章及配图归档](docs/reference/)保留原文来源与版权声明，权利归原权利人所有，使用条件以原文声明为准。比赛轨迹与活动对比的来源见各示例说明。
