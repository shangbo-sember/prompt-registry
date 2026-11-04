# 新人上手（10 分钟）

## 1. 先看一条现成的 prompt

打开 `prompts/image/cover-tech-hero/`，三个文件的关系：

- `meta.yaml` —— 这条 prompt 的身份证：ID、用途、尺寸、当前版本、状态。
- `versions/v1.md`、`v2.md` —— 每一版的实际文本，`v1` 已经弃用，能直接看到弃用原因。
- `prompt.md` —— 当前生效版的快照，复制粘贴就能用，不用自己翻目录找最新版。

## 2. 改一版试试

```bash
python3 scripts/new_version.py --prompt cover-tech-hero \
  --note "背景从纯色改成半透明玻璃质感"
```

执行后：

- 生成 `versions/v3.md`，里面已经填好上一版全文，你只改需要改的部分，并在开头补全「相对上一版改动」。
- `meta.yaml` 的 `current_version` 自动变成 3，状态回到「候选」。
- `prompt.md` 同步刷新。

旧版 `v2.md` **不会被动**。这就是留痕。

## 3. 跑校验

```bash
python3 scripts/validate.py
```

校验项：ID 是否重复、版本号是否连续、状态是否合法、弃用是否写了原因、`prompt.md` 是否和当前版本对得上、比例尺寸是否在允许范围。全绿才能提 PR。

## 4. 跑回归核对表

```bash
python3 evals/run_eval.py --prompt cover-tech-hero
```

在 `evals/results/` 生成一份逐条核对表。用新版本出图，按 `evals/rubric.md` 打勾打分，把结论填回去。

## 5. 提 PR

按模板填四项：改哪条 prompt、从哪版到哪版、改了什么、回归结论。评审看的是回归结论，不是文采。

## 常见疑问

**Q：只是改个标点，也要升版吗？**
要。升版成本很低（一条命令），但"这版图是哪段文字出的"必须能对上。

**Q：图放哪？**
图不进仓库。定稿图和弃用留痕都记在飞书多维表格台账，仓库只存 prompt 文本与结论。

**Q：能用别人的 prompt 改吗？**
可以，但必须新起一条 ID 或新起一版，并写明来源。不要把别人的 prompt 覆盖进已有版本。
