#!/usr/bin/env python3
"""回归核对表生成器。

当前阶段：人工执行。脚本负责把用例展开成一张可打印、可回填的核对表。
后续接自动化：在这里接入生图接口批量出图 + 视觉断言，用例文件格式不用改。

用法：
    python3 evals/run_eval.py --prompt cover-tech-hero
    python3 evals/run_eval.py --prompt PRM-IMG-001 --version 2
"""

import argparse
import datetime as dt
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts" / "image"
CASES_DIR = ROOT / "evals" / "cases"
RESULTS_DIR = ROOT / "evals" / "results"


def resolve(target):
    d = PROMPTS_DIR / target
    if d.is_dir():
        return d
    for p in PROMPTS_DIR.iterdir():
        meta = p / "meta.yaml"
        if p.is_dir() and meta.exists():
            data = yaml.safe_load(meta.read_text(encoding="utf-8")) or {}
            if str(data.get("id")) == target:
                return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True, help="slug 或 ID")
    ap.add_argument("--version", type=int, default=None, help="被测版本，默认取当前生效版")
    ap.add_argument("--auto", action="store_true", help="自动执行（尚未接入）")
    args = ap.parse_args()

    if args.auto:
        print("自动执行尚未接入。需要配置生图接口与视觉断言后才能开启；")
        print("在此之前请用默认模式生成核对表，人工逐条核对。")
        return 2

    d = resolve(args.prompt)
    if not d:
        print(f"找不到 prompt：{args.prompt}")
        return 1

    meta = yaml.safe_load((d / "meta.yaml").read_text(encoding="utf-8")) or {}
    version = args.version or meta.get("current_version")
    version_file = d / "versions" / f"v{version}.md"
    if not version_file.exists():
        print(f"版本文件不存在：{version_file}")
        return 1

    cases_file = CASES_DIR / f"{d.name}.cases.yml"
    if not cases_file.exists():
        print(f"缺少用例文件：{cases_file}")
        print("没有用例就没有回归，先按 requirement.must_have / avoid 补一份。")
        return 1

    data = yaml.safe_load(cases_file.read_text(encoding="utf-8")) or {}
    cases = data.get("cases") or []
    total_checks = sum(len(c.get("checks") or []) for c in cases)

    today = dt.date.today().isoformat()
    out = RESULTS_DIR / f"{d.name}-v{version}-{today}.md"
    n = 2
    while out.exists():
        out = RESULTS_DIR / f"{d.name}-v{version}-{today}-r{n}.md"
        n += 1

    lines = [
        f"# 回归核对表 · {meta.get('title')}",
        "",
        f"- prompt ID：{meta.get('id')}",
        f"- 被测版本：v{version}",
        f"- 用途 / 比例：{meta.get('use')} / {meta.get('aspect_ratio')}",
        f"- 执行日期：{today}",
        "- 执行人：",
        "- 出图张数：",
        "",
        "> 打分标准见 evals/rubric.md。每项写清「为什么」，不要只写分数。",
        "",
    ]

    for c in cases:
        lines.append(f"## {c.get('case_id')} · {c.get('intent')}")
        lines.append("")
        lines.append("| 检查项 | 通过 | 说明 |")
        lines.append("| --- | --- | --- |")
        for chk in c.get("checks") or []:
            lines.append(f"| {chk} | 待填 |  |")
        lines.append("")

    lines += [
        "## 评分",
        "",
        "| 必现元素 | 禁忌命中 | 文字正确性 | 风格一致性 | 可直接用性 | 合计 |",
        "| --- | --- | --- | --- | --- | --- |",
        "|  |  |  |  |  | /10 |",
        "",
        "## 结论",
        "",
        "- [ ] 通过（≥8 分），进入候选",
        "- [ ] 有条件通过（6-7 分），妥协点：",
        "- [ ] 不通过（<6 分），原因：",
        "",
        "## 备注",
        "",
    ]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")

    print(f"已生成核对表：{out.relative_to(ROOT)}")
    print(f"用例 {len(cases)} 组、检查项 {total_checks} 条，请出图后逐条回填。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
