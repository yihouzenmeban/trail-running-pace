# Skills 行为评测

[简体中文](guide.md) | [English](guide.en.md)

本指南面向 Skills 维护者。日常生成配速表无需读取评测材料。下列命令以仓库根目录为工作目录。

## 用例与输入

[cases.json](cases.json) 提供五组中英文提示词，覆盖默认值、出发时间与括号内容独立、明确到达时间、替换旧目标列表和保留 `0/false`。所有用例使用同目录的合成轨迹 [course.gpx](course.gpx)。

## 执行步骤

1. 为每个用例和语言开启独立 AI 会话，加载 `even-effort-pace-chart`。
2. 只提供该语言的提示词、轨迹和用例中的 `selected_config`（若有），不提供预期结果。
3. 保留 AI 实际写出的配置与执行记录，然后运行检查器：

```bash
python3 skills/even-effort-pace-chart/evals/evaluate.py \
  --case start_does_not_select_arrival --config outputs/candidate.json
```

`--case` 使用用例 ID，`--config` 指向该会话实际生成的配置。退出码 `0` 表示配置符合用例，`1` 表示不符合，`2` 表示调用或文件错误。

## 人工复核与记录

人工检查执行记录：是否先检查轨迹、是否对已有默认值提出多余追问、是否生成了要求的文件，以及是否读取核对摘要。记录模型版本、语言、用例 ID、检查器结果和人工复核结论。

检查器离线运行，不调用 AI，也不验证执行记录或实际文件。单元测试证明检查器能够识别正确和错误配置，不代表自然语言评测已经通过。
