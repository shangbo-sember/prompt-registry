#!/usr/bin/env python3
"""一键升版：绝不覆盖旧版本，只为新版本建档。

用法：
    python3 scripts/new_version.py --prompt cover-tech-hero \
        --note "主光改暖调，标题缩到 6 字" \
        --deprecate-previous --reason "冷调在信息流里辨识度低"

    # 只升版、不弃用旧版（旧版继续保留为候选）
    python3 scripts/new_version.py --prompt PRM-IMG-002 --note "背景改浅灰"
"""

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts" / "image"


def split_frontmatter(text):
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("版本文件缺少 frontmatter")
    return yaml.safe_load(parts[1]) or {}, parts[2]


def resolve_prompt_dir(target):
    by_slug = PROMPTS_DIR / target
    if by_slug.is_dir():
        return by_slug
    for d in PROMPTS_DIR.iterdir():
        meta_path = d / "meta.yaml"
        if d.is_dir() and meta_path.exists():
            meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
            if str(meta.get("id")) == target:
                return d
    return None


def dump_frontmatter(data):
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True, help="prompt 的 slug 或 ID")
    ap.add_argument("--note", required=True, help="相对上一版的改动点，写清改了什么")
    ap.add_argument("--why", default="", help="为什么改（可选，会写进改动说明）")
    ap.add_argument("--author", default="", help="提交人")
    ap.add_argument("--deprecate-previous", action="store_true", help="把上一版标记为弃用")
    ap.add_argument("--reason", default="", help="弃用上一版的原因，标记弃用时必填")
    args = ap.parse_args()

    d = resolve_prompt_dir(args.prompt)
    if not d:
        print(f"找不到 prompt：{args.prompt}")
        return 1

    meta_path = d / "meta.yaml"
    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    vdir = d / "versions"

    existing = sorted(
        [p for p in vdir.glob("v*.md") if re.fullmatch(r"v\d+", p.stem)],
        key=lambda p: int(p.stem[1:]),
    )
    if not existing:
        print("没有可参照的上一版，首版请手工创建 v1.md")
        return 1

    last_num = int(existing[-1].stem[1:])
    new_num = last_num + 1
    last_file = existing[-1]
    last_fm, last_body = split_frontmatter(last_file.read_text(encoding="utf-8"))

    if args.deprecate_previous and len(args.reason.strip()) < 8:
        print("要弃用上一版就必须给 --reason，并写清哪里不达标")
        return 1

    today = dt.date.today().isoformat()

    # 1. 必要时标记上一版为弃用（只改状态与原因，绝不删改正文）
    if args.deprecate_previous:
        last_fm["status"] = "弃用"
        last_fm["deprecated_reason"] = args.reason.strip()
        last_fm["deprecated_at"] = today
        _, raw_body = split_frontmatter(last_file.read_text(encoding="utf-8"))
        last_file.write_text(
            f"---\n{dump_frontmatter(last_fm)}\n---\n{raw_body}", encoding="utf-8"
        )
        print(f"已把 v{last_num} 标记为弃用（正文未改动）")

    # 2. 生成新版骨架：继承上一版正文，改动点留空待填
    new_fm = {
        "id": meta.get("id"),
        "version": new_num,
        "status": "候选",
        "created_at": today,
        "author": args.author or last_fm.get("author", ""),
        "aspect_ratio": last_fm.get("aspect_ratio") or meta.get("aspect_ratio"),
        "image_size": last_fm.get("image_size") or meta.get("image_size"),
    }
    note_block = f"1. {args.note.strip()}"
    if args.why.strip():
        note_block += f"\n   原因：{args.why.strip()}"
    note_block += f"\n2. 上一版（v{last_num}）已冻结，如需回看他那一版效果请看 versions/v{last_num}.md。"

    prompt_body = last_body
    if "# Prompt 正文" in prompt_body:
        prompt_body = "# Prompt 正文" + prompt_body.split("# Prompt 正文", 1)[1]

    new_text = (
        f"---\n{dump_frontmatter(new_fm)}\n---\n\n"
        f"## 相对上一版改动\n\n{note_block}\n\n"
        f"## 参考素材\n\n继承 v{last_num}，如无变化写“同 v{last_num}”。\n\n"
        f"{prompt_body.lstrip()}"
    )
    new_file = vdir / f"v{new_num}.md"
    if new_file.exists():
        print(f"{new_file.name} 已存在，拒绝覆盖")
        return 1
    new_file.write_text(new_text, encoding="utf-8")

    # 3. 更新 meta 与 prompt.md 快照
    meta["current_version"] = new_num
    meta["status"] = "候选"
    meta["updated_at"] = today
    meta_path.write_text(dump_frontmatter(meta) + "\n", encoding="utf-8")

    snapshot = (
        f"<!-- 当前生效版快照：由 scripts/new_version.py 从 versions/v{new_num}.md 同步生成，请勿手改 -->\n"
        f"<!-- 版本状态：候选 | 更新于：{today} -->\n\n"
        + prompt_body.replace("# Prompt 正文", "").strip()
        + "\n"
    )
    (d / "prompt.md").write_text(snapshot, encoding="utf-8")

    print(f"已生成 versions/v{new_num}.md，current_version 更新为 v{new_num}，prompt.md 已同步")
    print("下一步：")
    print(f"  1. 编辑 versions/v{new_num}.md，改掉需要改的提示词，并补全改动点")
    print("  2. python3 scripts/validate.py")
    print(f"  3. python3 evals/run_eval.py --prompt {d.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
