# 生图 Prompt 仓库（Prompt as Code）

品牌部内容团队的**生图提示词资产库**。把提示词当代码管：一条 prompt 一个 ID，改动留痕、版本可回溯、改动前后能跑回归比对。

## 三条硬约定

1. **一条 prompt 一个 ID**，形如 `PRM-IMG-001`，全仓库唯一，永不复用。
2. **改了就升版**，旧版本文件只增不改、永不删除、永不覆盖。
3. **合并进 `main` 的版本才算生效版本**，改动走 PR，带回归结论。

## 目录结构

```
prompts/image/<slug>/        一条 prompt 一个目录
  meta.yaml                  元信息：ID、用途、尺寸、状态、当前版本、关联内容
  prompt.md                  当前生效版快照（由脚本生成，供人直接复制使用）
  versions/v1.md v2.md ...   每个历史版本，只增不改

evals/                       回归测试
  cases/*.yml                每条 prompt 的断言用例（必现元素 / 禁忌 / 构图）
  rubric.md                  人工评分标准
  run_eval.py                生成核对表，自动化接口已预留
  results/                   每次回归的结论留档

scripts/
  validate.py                校验规则，提交前和 CI 都跑
  new_version.py             一键升版，自动生成骨架

docs/                        规则细则与上手说明
.github/                     PR 检查清单与 CI
```

## 日常三步

```bash
# 1. 改 prompt：自动升版，生成新版本骨架并标记旧版
python3 scripts/new_version.py --prompt cover-tech-hero \
  --note "主光改暖调，标题文字减到 6 字以内" --deprecate-previous --reason "冷调在信息流里辨识度低"

# 2. 自检：命名、编号、版本连续性、状态合法性、prompt 快照是否同步
python3 scripts/validate.py

# 3. 提 PR：按 .github/PULL_REQUEST_TEMPLATE.md 填写改动点与回归结论
```

## 回归测试怎么跑

当前阶段：**框架可用，人工执行**。

1. 改完 prompt 后运行 `python3 evals/run_eval.py --prompt cover-tech-hero`，会生成一份「逐条核对表」到 `evals/results/`。
2. 用新版本出图，按 `evals/rubric.md` 逐条打勾、打分。
3. 结论填回核对表并提交到 PR；不通过的必须给结论，不能只写"已看"。

后续接自动化：在 `run_eval.py` 里接生图接口批量出图 + 接视觉模型做断言，用例和断言写法不变，只换执行方式。

## 与飞书台账的分工

| 载体 | 管什么 |
| --- | --- |
| 本仓库 | prompt 文本本身怎么演进、怎么回归验证 |
| 飞书多维表格台账 | 哪张图定稿、弃用原因、关联哪篇内容、发布后数据 |

**图片文件不进仓库**（体积大、无法 diff）。仓库只存文本与结论。

## 新人上手

读 `docs/getting-started.md`，10 分钟能跑通第一条 prompt 的升版。
