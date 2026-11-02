# 实际活动与配速方案对比

[简体中文](comparison.md) | [English](comparison.en.md)

使用同目录 `../scripts/compare_activity.py`，复用 `pace_chart.py` 的路线清理、CP 选择、距离、爬升和配速模型。支持 GPX/KML、嵌入或人工 CP，无须修改已有比赛配置。对比功能需要可选依赖，常规配速表仍只用标准库：

```bash
python3 -m pip install -r <skill-dir>/scripts/requirements-comparison.txt
```

## 离线检查和生成

提供比赛轨迹、现有配速配置、单活动原始 FIT 或仅包含一个 FIT 的 ZIP。可选提供佳明活动详情 JSON；省略时使用 FIT session 汇总并标记来源。`--targets` 是精确目标列表，覆盖配置中的 `target`/`targets`，不会展开为五组，也不改写原配置。未指定则使用该配置的目标与默认逻辑。

```bash
python3 <skill-dir>/scripts/compare_activity.py inspect race.gpx \
  --config race.json --fit activity-original.zip --summary activity-details.json \
  --targets 15:00 16:00 17:00

python3 <skill-dir>/scripts/compare_activity.py generate race.gpx \
  --config race.json --fit activity-original.zip --summary activity-details.json \
  --targets 15:00 16:00 17:00 --output-dir output/comparison
```

`inspect` 输出活动汇总、匹配后的站点、逐段时间及地形数据、告警；不写文件。`generate` 默认仅写 `garmin-comparison.svg`，依次展示：

顶部集中展示实际完赛时间，以及各目标下的最终领先／落后时长。正文分为两节：

1. **时间表现**：每个目标一张累计差距曲线，每行最多三张；随后是一张区间耗时图表，每个 CP 区间一行，将实际耗时、各目标计划耗时、快慢文字与差距横条放在一起。精确累计到站时间保留在曲线点的提示中。
2. **赛道数据对比**：全程汇总下展示累计距离差和本段爬升、下降。累计距离用围绕零线的差值条，旁边保留佳明、仓库累计公里数；爬升、下降用成对横条，并列出双方数值与差值。各行采用同一距离差刻度；爬升、下降共用一套从零开始的刻度。

时间的绿色表示实际领先／本段更快，红色表示实际落后／本段更慢，持平为灰色，并用文字注明状态。累计曲线按赛道距离对齐 CP，各目标共用刻度，零线上方领先、下方落后；跨零线处分色。区间快慢条共用一套对称刻度，零线左侧为慢、右侧为快，文字保留到秒。地形用深灰代表佳明、蓝色代表仓库，差值明确写「仓库多／少」，不赋予好坏含义；未知显示 `—`，不绘制对应数值条或差值条。

浏览器独立打开 SVG 时，可悬停或用 Tab 聚焦曲线点、区间单元格和地形单元格；提示包含时间或数值。静态图片仍可直接阅读区间耗时、快慢差距和地形数据；精确累计到站时间需查看曲线提示。脚注仅保留关键口径，完整来源与告警位于提示和 SVG 元数据中，不额外生成 HTML，不依赖外部图表库。

时间差以**实际表现**解读：`方案 − 佳明 > 0` 表示实际领先／本段快，`< 0` 表示实际落后／本段慢。绝对差小于半秒时按「持平 00:00:00」显示。地形差值为 **仓库 − 佳明**，先用原值相减再取整到米。时间按秒显示，支持超过 24 小时。需要未取整的结构化结果时加 `--export-json`；额外导出的 `garmin-comparison.json` 保留原有 `方案 − 实际` 差值，不包含原始 GPS 记录，但包含活动身份、匹配时间及估算指标。已有文件需要另一输出目录或授权的 `--overwrite`。

## CP 匹配与耗时口径

嵌入 CP 使用原站点坐标；人工 CP 和明确配置了 `distance_km` 的 CP 使用处理后路线对应距离的坐标。活动投影使用几何距离定位，再插值活动记录中的距离和经过时间，不将几何距离当成佳明距离。

多次经过同一站点、距活动轨迹超过 100 m、站点附近明显停留或站序不递增时，脚本返回诊断，不静默选最近一次。站内停留附近的不同投影也可能产生几秒误差，自动匹配不代表官方打卡。

确认实际经过时刻后提供 JSON 覆盖。键必须是 `inspect`/诊断中的 CP ID，不能使用站名或顺序猜测；值为 `H:MM[:SS]` 或保留小数精度的经过秒数：

```json
{
  "wpt:3": "03:08:35",
  "manual:2": 16638.987685
}
```

```bash
python3 <skill-dir>/scripts/compare_activity.py generate race.gpx \
  --config race.json --fit activity.fit --targets 15:00 16:00 17:00 \
  --passage-overrides passages.json --output-dir output/comparison
```

覆盖只允许中间 CP，时间必须在 GPS 记录覆盖范围内并保持站序；起终点采用活动开始/结束。活动起终点必须距路线端点不超过 100 m；录制范围不符时需选择合适的活动或路线。覆盖、偏移和输入哈希写入图表元数据，便于追溯。可以用经过秒数保留既有核对结果的精度。

实际分段耗时为 `本站经过时间 − 上站经过时间`，方案分段耗时为 `本站计划到达 − 上站计划到达`，包含上一站配置的停留。两者都包含站点之间的停留，不能据此拆出纯移动时间或站内停留。先用原值相减，再四舍五入显示；原值分段和等于全程，显示值之和可能相差几秒。

## 地形指标与输入限制

佳明中间 CP 的累计爬升/下降由 FIT 逐圈累计距离进行线性插值，再相减得到本段值；无法确定爬升在一圈内的具体位置。缺少逐圈距离会禁用中间地形估算；缺少某项爬升/下降会使后续相应累计值未知。未知显示 `—`，不补零，不自行按海拔重算佳明指标。

有平台详情时，终点优先使用其中存在的汇总字段，其他字段回退 FIT session；没有平台详情则全部使用 session。逐圈和平台总值可能不同，报告差异，不按比例缩放；若导致累计爬升/下降倒退则拒绝生成。缺失 GPS/时间/距离的记录会跳过并报告，跨越较长记录间隔时告警。损坏 FIT、多 session、记录距离/时间倒退会报错。

## 佳明在线读取

只在用户要求获取活动时使用 `list`/`fetch`。从 `GARMIN_PERSONAL_API_KEY` 环境变量读取密钥；或显式 `--env-file .env.local`。环境变量优先，不执行 env 文件里的命令或变量展开，不将凭据写进代码、配置或命令行参数。原始活动放在 Git 忽略的 `output/`，不要把完整个人轨迹提交到公开仓库。

```bash
python3 <skill-dir>/scripts/compare_activity.py list \
  --start-date 2026-10-01 --end-date 2026-11-02 --limit 20 --env-file .env.local

python3 <skill-dir>/scripts/compare_activity.py fetch <activity-id> --env-file .env.local
```

`list` 返回活动列表，可用 `--start` 和 `--limit` 分页。`fetch` 默认保存到 `output/activities/<activity-id>/`，生成 `activity-details.json` 和 `activity-original.zip`；可用 `--output-dir` 覆盖目录，已有缓存需要 `--overwrite`。文件权限为 `600`，bearer token 仅留在进程内。

默认区域 `--region com`；中国区显式 `--region cn`。失败不会自动切区或重试。`--timeout` 默认 45 秒。认证/网络错误只报告状态，不输出响应正文、密钥或 token。
