#!/usr/bin/env python3
"""Prompt 仓库校验：把版本与状态规则变成可自动检查的断言。

用法：
    python3 scripts/validate.py            # 校验全仓库
    python3 scripts/validate.py --quiet    # 只输出问题

退出码：0 = 全部通过；1 = 存在违规。
"""

import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts" / "image"

ALLOWED_STATUS = {"候选", "选中", "弃用"}
ALLOWED_RATIO = {"1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"}
ALLOWED_SIZE = {"1K", "2K", "4K"}
REQUIRED_META = [
    "id", "slug", "title", "use", "aspect_ratio", "image_size",
    "status", "current_version", "owner", "requirement",
]


def split_frontmatter(text):
    """拆出 YAML frontmatter 与正文。没有 frontmatter 返回 (None, text)。"""
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    return parts[1], parts[2]


def errors_append(errors, slug, msg):
    errors.append(f"[{slug}] {msg}")


def check_prompt_dir(slug, errors, warnings, seen_ids, seen_slugs):
    d = PROMPTS_DIR / slug
    meta_path = d / "meta.yaml"

    if not meta_path.exists():
        errors_append(errors, slug, "缺少 meta.yaml")
        return

    try:
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        errors_append(errors, slug, f"meta.yaml 解析失败：{exc}")
        return

    # 1. 必填字段
    for key in REQUIRED_META:
        if key not in meta or meta[key] in (None, ""):
            errors_append(errors, slug, f"meta.yaml 缺少必填字段 {key}")

    # 2. ID 格式与唯一性
    pid = str(meta.get("id", ""))
    if not re.fullmatch(r"PRM-IMG-\d{3}", pid):
        errors_append(errors, slug, f"ID 格式不合规：{pid!r}，应为 PRM-IMG-001 这种形式")
    if pid in seen_ids:
        errors_append(errors, slug, f"ID 重复：{pid} 已被 {seen_ids[pid]} 使用")
    else:
        seen_ids[pid] = slug

    # 3. slug 与目录名一致
    if meta.get("slug") != slug:
        errors_append(errors, slug, f"slug 与目录名不一致：meta={meta.get('slug')!r} dir={slug!r}")
    if slug in seen_slugs:
        errors_append(errors, slug, "slug 重复")
    seen_slugs.add(slug)

    # 4. 比例与尺寸白名单
    ratio = str(meta.get("aspect_ratio", ""))
    if ratio not in ALLOWED_RATIO:
        errors_append(errors, slug, f"aspect_ratio 不在允许范围：{ratio!r}")
    size = str(meta.get("image_size", ""))
    if size not in ALLOWED_SIZE:
        errors_append(errors, slug, f"image_size 不在允许范围：{size!r}")

    # 5. 状态合法
    status = meta.get("status")
    if status not in ALLOWED_STATUS:
        errors_append(errors, slug, f"status 非法：{status!r}，只能是 候选/选中/弃用")

    # 6. requirement 结构
    req = meta.get("requirement") or {}
    must_have = req.get("must_have") or []
    avoid = req.get("avoid") or []
    if not must_have:
        errors_append(errors, slug, "requirement.must_have 为空：没有必现要求就无法做回归")
    overlap = set(must_have) & set(avoid)
    if overlap:
        errors_append(errors, slug, f"必现要求与禁忌冲突：{sorted(overlap)}")

    # 7. 版本文件连续性
    vdir = d / "versions"
    if not vdir.exists():
        errors_append(errors, slug, "缺少 versions 目录")
        return
    version_files = sorted(
        [p for p in vdir.glob("v*.md") if re.fullmatch(r"v\d+", p.stem)],
        key=lambda p: int(p.stem[1:]),
    )
    if not version_files:
        errors_append(errors, slug, "没有任何版本文件")
        return
    expected = list(range(1, len(version_files) + 1))
    actual = [int(p.stem[1:]) for p in version_files]
    if actual != expected:
        errors_append(errors, slug, f"版本号不连续：实际 {actual}，应为 {expected}")

    # 8. 逐版检查
    current = meta.get("current_version")
    for vf in version_files:
        vnum = int(vf.stem[1:])
        try:
            fm_text, body = split_frontmatter(vf.read_text(encoding="utf-8"))
            fm = yaml.safe_load(fm_text) if fm_text else None
        except yaml.YAMLError as exc:
            errors_append(errors, slug, f"{vf.name} frontmatter 解析失败：{exc}")
            continue
        if not fm:
            errors_append(errors, slug, f"{vf.name} 缺少 frontmatter")
            continue

        if fm.get("id") != pid:
            errors_append(errors, slug, f"{vf.name} 的 id 与 meta 不一致：{fm.get('id')!r}")
        if fm.get("version") != vnum:
            errors_append(errors, slug, f"{vf.name} 的 version 字段应为 {vnum}，实际 {fm.get('version')!r}")

        vstatus = fm.get("status")
        if vstatus not in ALLOWED_STATUS:
            errors_append(errors, slug, f"{vf.name} 状态非法：{vstatus!r}")
        if vstatus == "弃用":
            reason = (fm.get("deprecated_reason") or "").strip()
            if len(reason) < 8:
                errors_append(errors, slug, f"{vf.name} 已弃用但弃用原因缺失或过于笼统（需写清哪里不达标）")

        for key in ("aspect_ratio", "image_size", "created_at", "author"):
            if not fm.get(key):
                errors_append(errors, slug, f"{vf.name} 缺少字段 {key}")
        if fm.get("aspect_ratio") and str(fm.get("aspect_ratio")) != ratio:
            warnings.append(f"[{slug}] {vf.name} 比例与 meta 不一致")

        # 提示词正文非空
        prompt_body = body.strip()
        if "# Prompt 正文" in prompt_body:
            prompt_body = prompt_body.split("# Prompt 正文", 1)[1].strip()
        if len(prompt_body) < 40:
            errors_append(errors, slug, f"{vf.name} Prompt 正文过短或缺失")

        # 升版说明
        if vnum > 1:
            if "相对上一版改动" not in body:
                errors_append(errors, slug, f"{vf.name} 缺少「相对上一版改动」小节")
            else:
                note = body.split("相对上一版改动", 1)[1]
                note = note.split("##", 1)[0].strip()
                if len(note) < 10:
                    errors_append(errors, slug, f"{vf.name} 「相对上一版改动」过于笼统，需写清改了什么、为什么")

    # 9. 当前版本必须存在且状态与 meta 对齐
    if current not in actual:
        errors_append(errors, slug, f"current_version={current!r} 没有对应版本文件")
    else:
        cur_file = vdir / f"v{current}.md"
        fm_text, _ = split_frontmatter(cur_file.read_text(encoding="utf-8"))
        cur_fm = yaml.safe_load(fm_text) or {}
        if cur_fm.get("status") != status:
            errors_append(
                errors, slug,
                f"meta.status={status!r} 与当前版 v{current} 状态 {cur_fm.get('status')!r} 不一致"
            )
        if cur_fm.get("status") == "弃用" and status == "弃用" and current == actual[-1]:
            warnings.append(f"[{slug}] 当前生效的最后一版已是弃用状态，确认是否需要另起新版或下架该 prompt")

    # 10. prompt.md 快照同步
    snap = d / "prompt.md"
    if not snap.exists():
        errors_append(errors, slug, "缺少 prompt.md 快照")
    else:
        text = snap.read_text(encoding="utf-8")
        m = re.search(r"versions/v(\d+)\.md", text)
        if not m:
            warnings.append(f"[{slug}] prompt.md 未标注来源版本号")
        elif int(m.group(1)) != current:
            errors_append(errors, slug, f"prompt.md 指向 v{m.group(1)}，但当前版本是 v{current}（快照未同步）")

    # 11. 定稿必须关联内容
    if status == "选中":
        ref = meta.get("content_ref") or {}
        for key in ("content_id", "content_title"):
            if not ref.get(key):
                errors_append(errors, slug, f"状态为选中但 content_ref.{key} 为空：定稿图必须能对上内容")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    errors, warnings = [], []
    seen_ids, seen_slugs = {}, set()

    if not PROMPTS_DIR.exists():
        print(f"找不到 prompt 目录：{PROMPTS_DIR}")
        return 1

    slugs = sorted([p.name for p in PROMPTS_DIR.iterdir() if p.is_dir()])
    if not slugs:
        print("prompt 目录为空")
        return 1

    for slug in slugs:
        check_prompt_dir(slug, errors, warnings, seen_ids, seen_slugs)

    if not args.quiet:
        print(f"校验 {len(slugs)} 条 prompt：{', '.join(slugs)}")
    for w in warnings:
        print(f"  提醒 {w}")
    for e in errors:
        print(f"  违规 {e}")

    if errors:
        print(f"\n未通过：{len(errors)} 项违规，{len(warnings)} 项提醒")
        return 1
    print(f"\n通过：规则全部满足（{len(warnings)} 项提醒）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
