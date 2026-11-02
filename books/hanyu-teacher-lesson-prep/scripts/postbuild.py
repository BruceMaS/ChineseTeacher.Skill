#!/usr/bin/env python3
"""postbuild.py — 在 cangjie 编译产物上追加「知识库层」，然后做校验与发布。

cangjie 的 compile_single 只认识 cards/overview/glossary，不认识本 skill 的 kb/（306 个分片、
5 MB 原文依据）。本脚本负责：

1. 调用 compile_single.build_tree 得到基线产物树；
2. 把 kb/ 复制到 references/kb/（raw 原文副本剥掉 OCR 页图链接，否则静态校验会报 1376 条 broken-ref）；
3. 在 SKILL.md 注入「知识库检索协议」段（说明先查索引、再读分片、命不中才回退原文）；
4. 跑 validate_skill_pack 硬校验；通过才原子替换 dist/<slug>/。

用法:
    python scripts/postbuild.py [--output single|pack]
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / ".cangjie" / "capabilities"
KB = ROOT / "kb"
SLUG = "hanyu-teacher-lesson-prep"
DIST_ROOT = ROOT.parents[1] / "dist"          # 个人文档/ChineseTeacher.Skill/dist
CANGJIE = Path.home() / ".workbuddy" / "skills" / "cangjie-skill"

KB_SECTION = """## 知识库（原文依据层，按需检索，勿通读）

本 Skill 自带一套可检索语料，共约 3 MB、306 个分片单元（63 语法点 + 201 辨析 + 42 课堂问题），
另含 4 种原文副本（`kb-raw/`，只收没有做分片的书）供按行号回查。
**任何涉及"具体怎么讲、学生实际会错成什么、这个词是否超纲、两个词怎么区分"的回答，都要落到这套语料上，而不是凭印象。**

目录（均为根下第一级，本包只用两级结构）：

| 目录 | 内容 |
|---|---|
| `kb-index/` | 索引表（先查这里，再看分片） |
| `kb-grammar/` | 语法点五段式分片（63） |
| `kb-discrimination/` | 易混辨析分片（201） |
| `kb-classroom/` | 课堂问题分片（42） |
| `kb-standards/` | 等级标准（能力描述、量化指标） |
| `kb-raw/` | 4 种原文副本（仅限无分片的书，按行号回查） |

检索协议（命中即停，禁止 `cat` 整个文件、禁止整目录读取）：

1. **先查索引**：`kb-index/` 下按主题找表——语法点 `grammar-points.md`、等级 `grammar-levels.md`、
   分级词表 `vocab-levels.tsv`、分级字表 `char-levels.tsv`、音节表 `syllables.tsv`、
   手写汉字表 `handwriting.tsv`、辨析 `discrimination.md`、课堂 `classroom.md`、
   拼音条款 `pinyin-rules.md`、面试 `interview.md`、跨文化 `cross-culture.md`。
2. **按码读分片**：每个分片 2–8 KB，就是一个完整知识单元，读一个即可回答一个问题。
   - 语法点 → `kb-grammar/<检索码>.md`（五段式完整单元）
   - 辨析 → `kb-discrimination/d<NNN>.md`（疑问→析疑→考考你）
   - 课堂问题 → `kb-classroom/c<NN>.md`
3. **命不中才回退原文**：先 `grep -n '关键词' kb-raw/<文件>` 拿行号，再读该行附近 ±80 行。
   - **`kb-raw/` 只有 4 种**：汉语拼音正词法、跨文化交际学概论、国教证书面试指南、对外汉语教学语法点汇总。
     语法手册、释疑 201 例、课堂技巧手册、等级标准**没有随包原文**——它们的正文已 1:1 收入分片
     （等级标准则已抽成分级表），改用 `grep -rl '关键词' kb-grammar/`（或 `kb-discrimination/`、`kb-classroom/`）定位分片。
   - 索引表的「行号」列是**节级锚点**（节标题所在行），不是内容行：命中后若 ±80 行内没有你要的正文，
     就在同一节内继续下探到下一个同级标题为止，不要因一次没读到就判定未收录。
   - 索引表可能混入目录页条目（行号指向目录而非正文）：读到的是目录或标题罗列时，
     改用 `grep -n` 在正文区重新定位。
4. **引用带出处**：分片头部有「来源：文件 + 行号」，回答时保留，教师才能核。

各层内容与质量警告（OCR 错误、缺条）见 `kb-index/README.md`，首次使用先读它。

"""

# ---------------------------------------------------------------- 布局：平台强制两级（根/二级目录/文件）
# 原 references/kb/grammar/x.md 是四级，上传报「目录层级超限」。改为根下平级目录。
KB_DIR = {
    "grammar": "kb-grammar",
    "discrimination": "kb-discrimination",
    "classroom": "kb-classroom",
    "index": "kb-index",
    "standards": "kb-standards",
    "raw": "kb-raw",
}

# 根级文件（SKILL.md / overview.md / PUBLICATIONS.md）里的 references/... 写法
ROOT_RULES = [
    ("references/capabilities/", "capabilities/"),
    ("references/kb/grammar/", "kb-grammar/"),
    ("references/kb/discrimination/", "kb-discrimination/"),
    ("references/kb/classroom/", "kb-classroom/"),
    ("references/kb/index/", "kb-index/"),
    ("references/kb/standards/", "kb-standards/"),
    ("references/kb/raw/", "kb-raw/"),
    ("references/overview.md", "overview.md"),
    ("references/glossary.md", "glossary.md"),
    ("references/cheatsheet.md", "cheatsheet.md"),
    ("references/capability-index.md", "capability-index.md"),
    ("references/kb/", "kb-"),
    ("references/", ""),
]

# overview.md 用「kb/index/x」这种相对根的写法
OVERVIEW_RULES = [
    ("kb/index/", "kb-index/"),
    ("kb/grammar/", "kb-grammar/"),
    ("kb/discrimination/", "kb-discrimination/"),
    ("kb/classroom/", "kb-classroom/"),
    ("kb/standards/", "kb-standards/"),
    ("kb/raw/", "kb-raw/"),
]

# capabilities/*.md 用「../kb/index/x」这种相对上溯的写法
CARD_RULES = [
    ("../kb/index/", "../kb-index/"),
    ("../kb/grammar/", "../kb-grammar/"),
    ("../kb/discrimination/", "../kb-discrimination/"),
    ("../kb/classroom/", "../kb-classroom/"),
    ("../kb/standards/", "../kb-standards/"),
    ("../kb/raw/", "../kb-raw/"),
    ("../kb/", "../kb-"),
    ("kb/index/", "../kb-index/"),          # 少数无 ../ 的叙述式引用
    ("references/capabilities/", "capabilities/"),
]

# kb-index/*.md 用同层相对写法（index/x、raw/x、grammar/）
IDX_RULES = [
    ("grammar/", "../kb-grammar/"),
    ("discrimination/", "../kb-discrimination/"),
    ("classroom/", "../kb-classroom/"),
    ("standards/", "../kb-standards/"),
    ("raw/", "../kb-raw/"),
    ("index/", ""),
]


def load_build_tree():
    spec = importlib.util.spec_from_file_location("compile_single", CANGJIE / "scripts" / "compile_single.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build_tree


IMG_BLOCK = re.compile(r"^\s*!\[[^\]]*\]\([^)]*\)\s*$")
IMG_INLINE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def strip_ocr_images(text: str, keep_lines: bool = False) -> str:
    """清掉 OCR 页图链接。

    keep_lines=True 时把整行图片替换为空行而不删除——raw/ 原文层依赖行号导航，
    任何删行都会让索引表的「行号」列整体偏移（曾导致语法手册偏移 643 行）。
    """
    out: list[str | None] = []
    for line in text.splitlines():
        if IMG_BLOCK.match(line):
            out.append("" if keep_lines else None)
        else:
            out.append(IMG_INLINE.sub("", line))
    if keep_lines:
        return "\n".join(x if x is not None else "" for x in out) + "\n"
    return "\n".join(x for x in out if x is not None) + "\n"


def copy_kb(dest_root: Path) -> tuple[int, int]:
    """把 kb/ 摊平复制到根下的 kb-*/ 目录（平台只允许两级）。"""
    files = 0
    size = 0
    for src in sorted(KB.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(KB)
        sub = rel.parts[0]
        if sub not in KB_DIR:
            raise SystemExit(f"[布局错误] kb/{sub}/ 未在 KB_DIR 中登记，请先在 postbuild.py 补映射")
        target = dest_root / KB_DIR[sub] / Path(*rel.parts[1:])
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix == ".md":
            # raw/ 下的原文副本必须保持行号不变，只清链接不删行
            keep = sub == "raw"
            text = strip_ocr_images(src.read_text(encoding="utf-8"), keep_lines=keep)
        else:
            text = None
        if text is None:
            shutil.copy2(src, target)
            size += target.stat().st_size
        else:
            target.write_text(text, encoding="utf-8")
            size += len(text.encode("utf-8"))
        files += 1
    return files, size


def flatten_tree(staging: Path) -> list[str]:
    """把编译产物里的 references/xxx 提升到根下，使其成为二级结构。"""
    ref = staging / "references"
    moved: list[str] = []
    if not ref.exists():
        return moved
    for item in sorted(ref.iterdir()):
        target = staging / item.name
        if target.exists():
            raise SystemExit(f"[布局错误] 提升 {item.name} 时目标已存在，请检查编译产物")
        item.rename(target)
        moved.append(item.name)
    ref.rmdir()
    return moved


def rewrite_refs(staging: Path) -> dict[str, int]:
    """按文件所在位置重写包内所有路径引用，避免搬目录后指向失效。"""
    counters: dict[str, int] = {}

    def apply(path: Path, rules: list[tuple[str, str]], tag: str) -> None:
        text = path.read_text(encoding="utf-8")
        n = 0
        for old, new in rules:
            if old in text:
                n += text.count(old)
                text = text.replace(old, new)
        if n:
            path.write_text(text, encoding="utf-8")
        counters[tag] = counters.get(tag, 0) + n

    for name in ("SKILL.md", "overview.md", "PUBLICATIONS.md", "glossary.md",
                 "cheatsheet.md", "capability-index.md"):
        p = staging / name
        if p.exists():
            apply(p, ROOT_RULES, "root")

    for p in sorted((staging / "capabilities").glob("*.md")):
        apply(p, CARD_RULES, "capabilities")

    for p in sorted((staging / "kb-index").glob("*.md")):
        apply(p, IDX_RULES, "kb-index")

    # overview.md 的 kb/xxx 写法和 ROOT_RULES 不重叠，单独过一遍更稳妥
    p = staging / "overview.md"
    if p.exists():
        apply(p, OVERVIEW_RULES, "overview")

    return counters


def check_links(staging: Path) -> list[str]:
    """全量扫描包内指向 kb-*/ 与 capabilities/ 的路径，报告目标不存在者。

    覆盖三种写法：markdown 链接 `[x](../kb-index/y.md)`、反引号路径 `` `kb-raw/z.md` ``、
    以及 grep 命令里的相对路径 `` `grep -n 'k' ../kb-raw/z.md` ``。
    """
    pat = re.compile(r"((?:\.\./)*(?:kb-[a-z]+|capabilities)/[^\s`'\"|)\]]+?\.(?:md|tsv))")
    bad: list[str] = []
    for p in sorted(staging.rglob("*.md")):
        for m in pat.finditer(p.read_text(encoding="utf-8")):
            tgt = m.group(1)
            if "<" in tgt or "*" in tgt:
                continue
            if not (p.parent / tgt).resolve().exists():
                bad.append(f"{p.relative_to(staging)} -> {tgt}")
    return bad


def inject_kb_section(skill_md: Path) -> None:
    text = skill_md.read_text(encoding="utf-8")
    if "## 知识库（原文依据层" in text:
        return
    anchor = "## 加载规则"
    if anchor not in text:
        raise SystemExit("SKILL.md 缺少「## 加载规则」锚点，编译器模板可能已变更，请人工检查")
    text = text.replace(anchor, KB_SECTION + anchor, 1)
    text = text.replace(
        "- 路由表与 capability-index.md 都无法命中的意图，明确告知超出本书范围，不要硬套。",
        "- 路由表与 capability-index.md 都无法命中的意图，明确告知超出本书范围，不要硬套。\n"
        "- **加载能力卡后，答案里的语言事实必须来自 `kb-*` 目录（`kb-grammar/` `kb-discrimination/` "
        "`kb-classroom/` `kb-index/` `kb-standards/` `kb-raw/`）**；能力卡只给方法与边界，"
        "具体例句、偏误、等级、条款一律回知识库取。取不到就说取不到。",
        1,
    )
    skill_md.write_text(text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="single", choices=["single", "pack"])
    args = ap.parse_args()

    build_tree = load_build_tree()
    DIST_ROOT.mkdir(parents=True, exist_ok=True)
    final = DIST_ROOT / SLUG
    staging = DIST_ROOT / f".staging-{datetime.now():%Y%m%d-%H%M%S}-{SLUG}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    files = build_tree(BUNDLE, args.output)
    for rel, content in files.items():
        p = staging / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    n, size = copy_kb(staging)
    moved = flatten_tree(staging)
    stats = rewrite_refs(staging)
    inject_kb_section(staging / "SKILL.md")

    print(f"[build] {len(files)} 个基线文件 + kb {n} 个文件（{size/1024/1024:.2f} MB）")
    print(f"[layout] 提升 {len(moved)} 项到根：{', '.join(moved)}")
    print(f"[refs] 重写引用 {stats}")

    broken = check_links(staging)
    if broken:
        print(f"[refs] 发现 {len(broken)} 处失效引用：")
        for b in broken[:15]:
            print("   ", b)
        print(f"[hard-gate] 引用校验未通过，保留 staging 供排查：{staging}")
        return 1

    depth = max(len(p.relative_to(staging).parts) for p in staging.rglob("*") if p.is_file())
    if depth > 3:
        print(f"[hard-gate] 目录层级 {depth} 层，超过平台上限 3（根/二级/文件）")
        return 1
    print(f"[layout] 最大文件层级 {depth}（根=1，平台上限 3）符合要求")

    rc = subprocess.run(
        [sys.executable, str(CANGJIE / "scripts" / "validate_skill_pack.py"), str(staging)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    print(rc.stdout.strip()[-3000:])
    if rc.returncode != 0:
        print(f"[hard-gate] 校验未通过，保留 staging 供排查：{staging}")
        return 1

    if final.exists():
        shutil.rmtree(final)
    staging.rename(final)
    total = sum(p.stat().st_size for p in final.rglob("*") if p.is_file())
    cnt = sum(1 for p in final.rglob("*") if p.is_file())
    print(f"[publish] {final}  {cnt} 个文件 / {total/1024/1024:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
