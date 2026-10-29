# 分段模型评估

[简体中文](pacing-validation.md) | [English](pacing-validation.en.md)

本工具检验“已知完赛时间时，各段如何分配”，不预测完赛能力。终点被强制对齐，因此只统计赛段和内部检查点误差。它不替代 [Skills 行为评测](guide.md)。

## 输入

准备本地 JSON。以下为合成示例，`distance_km` 和 `ascent_m` 均是**该段增量**，不是累计值；各段必须连续覆盖整次活动。停留属于该段终点，最后一段停留必须为零。

```json
{
  "activities": [
    {
      "id": "training-example",
      "split": "train",
      "time_basis": "moving",
      "segments": [
        {"distance_km": 5, "ascent_m": 200, "seconds": 3000, "rest_seconds": 120},
        {"distance_km": 5, "ascent_m": 0, "seconds": 2400}
      ]
    },
    {
      "id": "validation-example",
      "split": "validation",
      "time_basis": "elapsed_unseparated",
      "segments": [
        {"distance_km": 5, "ascent_m": 100, "seconds": 2700},
        {"distance_km": 5, "ascent_m": 0, "seconds": 2500}
      ]
    }
  ]
}
```

- `moving`：`seconds` 是移动时间，`rest_seconds` 是额外、已确认的终点停留，默认 0；不要把总经过时间填进移动时间。
- `elapsed_unseparated`：`seconds` 包括无法可靠分离的停留，只能作探索性比较；`rest_seconds` 必须为 0，避免重复计时。
- `terrain_factor` 可按段明确提供，默认 1，必须不小于 1。难度范围跨越赛段时先拆段，不要用简单平均系数替代工作量积分。
- 每次活动至少两段；距离、秒数必须有限且大于零，爬升和停留非负。活动 ID 必须唯一，不能换个 ID 将同一次活动放进两个集合。

原始轨迹与观测文件保留在仓库外。优先使用比赛官方 CP 记录或可区分计时器停留的活动记录；训练中的休息、间歇和拍照不等于疲劳。只有 GPX 时间戳时，不根据低速武断地把陡坡行走当成停留。统一海拔处理口径，明确分段方法和缺失点处理。

## 执行

```bash
python3 skills/even-effort-pace-chart/evals/evaluate_pacing.py \
  --observations /path/to/private-observations.json
```

默认比较旧幂曲线 0.08，与线性模型的 `fatigue_half_slowdown` 为 0、0.08、0.16、0.24、0.4 的方案。也可通过 `--candidates /path/to/candidates.json` 提供配置对象列表；仅接受 `fatigue_model`、该模型的疲劳参数及 `ascent_km_per_100m`。

输出为聚合 JSON，不导出活动 ID、坐标或逐次活动详情。退出码 0 表示评估完成，2 表示输入错误。不会修改配置、训练数据或默认值。

## 判断依据

在看结果前固定完整活动的划分，例如较早的 80% 训练、较新的 20% 验证；不能随机拆同一活动的赛段。每组至少一次活动，但少量活动的结果不稳定。若反复查看验证结果调参，需要新的独立测试集。

| 输出 | 含义 |
| --- | --- |
| `selected_index` | 仅按训练集 `mean_segment_wape` 选择的候选索引，从 0 开始；并列时取输入顺序首项 |
| `mean_segment_wape` | 每次活动的分段绝对误差之和 / 总观测秒数，再对活动等权平均；0.1 表示 10% |
| `mean_segment_mae_seconds` | 先求每次活动的分段平均绝对秒数误差，再对活动等权平均 |
| `mean_checkpoint_mae_seconds` | 内部检查点累计到达时间的平均绝对误差，排除起点和强制对齐的终点 |
| `mean_checkpoint_mae_fraction` | 内部检查点误差 / 总观测秒数，再对活动等权平均 |
| `time_basis_counts` | 两种时间口径的活动数；混合口径应另外分组复核 |

已确认的停留在预测与观测中各计一次，不参与疲劳拟合。未分离停留会混入曲线误差。评估比较的是时间分配，不验证基础等效距离是否为生理真值，也不推断下坡与路面系数。对单个选手拟合更好，不足以证明应修改公开工具的默认参数。
