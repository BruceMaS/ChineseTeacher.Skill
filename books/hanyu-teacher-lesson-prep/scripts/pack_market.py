#!/usr/bin/env python3
"""pack_market.py — 把已构建的 skill 打包成 WorkBuddy 开放平台上架用的 zip。

与本地安装版（dist/<slug>/）的差异：

1. **frontmatter 补市场字段**：display_name / display_name_en / description_zh /
   description_en / examples_zh / examples_en / version / author（本地只要 name + description）。
2. **附 PUBLICATIONS.md**（出版物清单与版权说明）到包根目录，并把其中的路径改成包内新布局。
3. 可选 **移除原文全文层**（`kb-raw/`），并把依赖它的指引改成「以正式出版物为准」。
   默认保留；加 `--no-raw` 才移除（用于未获授权仍要公开分发的场景）。

目录布局：平台只允许「根目录/二级目录/文件」，所以包内是 `capabilities/`、`kb-index/`、
`kb-grammar/` 等平级目录，最大层级 2。

用法:
    python scripts/pack_market.py --author "Bruce" --version 1.0.0 \
        --desc-zh "简介第一句。简介第二句。"
    python scripts/pack_market.py --author "Bruce" --version 1.0.0 --desc-zh "..." --no-raw
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT.parents[1] / "dist"
SLUG = "hanyu-teacher-lesson-prep"
SRC = DIST / SLUG
OUT_DIR = DIST / "market"
CANGJIE = Path.home() / ".workbuddy" / "skills" / "cangjie-skill"
PUBLICATIONS = ROOT / "PUBLICATIONS.md"

DISPLAY_ZH = "汉语教师备课知识库"
DISPLAY_EN = "Chinese Teacher Lesson Prep"
DESC_EN = (
    "A retrieval-ready knowledge base distilled from Chinese-language teaching handbooks: lesson "
    "design for graded grammar points, confusable-pair analysis, error prediction, practice ladders, "
    "demo-lesson scripts, pinyin orthography and classroom diagnosis."
)
EXAMPLES_ZH = [
    "中级班讲「把」字句，45 分钟，帮我按五段式备课，并告诉我这个点属几级。",
    "学生问「以前」和「以后」有什么区别、还有「以来」怎么用，给我区分标准和检验题。",
    "「北京大学的留学生」拼音怎么连写？「西安」要不要加隔音符号？依据哪一条？",
]
EXAMPLES_EN = [
    "Design a 45-minute lesson on the ba-construction for an intermediate class, and tell me its level.",
    "A student asks the difference between 以前, 以后 and 以来. Give me criteria plus a check-up exercise.",
    "How should '北京大学的留学生' be written in pinyin? Which clause of GB/T 16159 applies?",
]

# 包根文件里把 references/... 写成新布局（与 postbuild.ROOT_RULES 同源）
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

IDX_RULES = [
    ("grammar/", "../kb-grammar/"),
    ("discrimination/", "../kb-discrimination/"),
    ("classroom/", "../kb-classroom/"),
    ("standards/", "../kb-standards/"),
    ("raw/", "../kb-raw/"),
]

CN_KG_NOTE = (
    "> **本包不含原文全文。** 为控制体积与版权风险，原文全文层已在发布版中移除；"
    "下表保留条款号与章节标题，用于定位与引用，具体表述以正式出版物为准。\n"
)


def must(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"[替换失败] {msg}——源文件结构已变，请检查 pack_market.py 的替换规则")


def apply_rules(path: Path, rules: list[tuple[str, str]]) -> int:
    text = path.read_text(encoding="utf-8")
    n = 0
    for old, new in rules:
        if old in text:
            n += text.count(old)
            text = text.replace(old, new)
    if n:
        path.write_text(text, encoding="utf-8")
    return n


# ---------- 索引表瘦身：三列（条款/行号/grep 命令）→ 一列（条款） ----------

def slim_index(path: Path, note: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    seen_table = False
    for line in lines:
        s = line.strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if set(s) <= set("|-: "):          # 分隔行
                out.append("|---|")
                continue
            if cells and cells[0] in ("条款/标题", "条款", "标题"):
                out.append("| 条款 / 章节 |")
                seen_table = True
                continue
            cell = re.sub(r"[,，、]?\s*例如\s*[：:]?\s*$", "", cells[0]).strip()
            out.append(f"| {cell} |")
            continue
        out.append(line)
    must(seen_table, f"{path.name} 未找到索引表头")

    text = "\n".join(out) + "\n"
    m = re.search(r"^\| 条款 / 章节 \|$", text, re.M)
    must(bool(m), f"{path.name} 未定位表头行")
    text = text[: m.start()] + note + "\n" + text[m.start():]
    text = re.sub(r"\n{3,}", "\n\n", text)
    path.write_text(text, encoding="utf-8")


# ---------- 移除原文层时改写依赖它的指引 ----------

def drop_raw(staged: Path) -> int:
    """删掉 kb-raw/ 并把所有依赖它的引用改成「以正式出版物为准」。返回改写处数。"""
    raw = staged / "kb-raw"
    if not raw.exists():
        raise SystemExit("[布局错误] 未找到 kb-raw/，请先跑 postbuild.py")
    shutil.rmtree(raw)

    changed = 0
    for name in ("cross-culture.md", "interview.md", "pinyin-rules.md"):
        p = staged / "kb-index" / name
        must(p.exists(), f"缺少索引表 kb-index/{name}")
        slim_index(p, CN_KG_NOTE)
        changed += 1

    # 其余索引表若含 raw 引用行，直接删掉该行（表中其余条目仍可用）
    for p in (staged / "kb-index").glob("*.md"):
        t = p.read_text(encoding="utf-8")
        kept = [l for l in t.splitlines() if "kb-raw" not in l]
        if len(kept) != len(t.splitlines()):
            p.write_text("\n".join(kept) + "\n", encoding="utf-8")
            changed += 1

    # SKILL.md：知识库段的副本声明与回退步骤
    md = staged / "SKILL.md"
    t = md.read_text(encoding="utf-8")
    t2 = re.sub(r"另含 \d+ 种原文副本[^\n]*\n", "本包**不含原文全文**，来源与版权见包根目录 `PUBLICATIONS.md`。\n", t)
    must(t2 != t, "SKILL.md 未见原文副本声明")
    t = t2

    old_step = (
        "3. **命不中才回退原文**：先 `grep -n '关键词' kb-raw/<文件>` 拿行号，再读该行附近 ±80 行。"
    )
    must(old_step in t, "SKILL.md 未见回退原文步骤")
    t = t.replace(
        old_step,
        "3. **命不中就说明未收录**：分片与索引表覆盖不到时，直接告诉用户「本包未收录该内容」，"
        "并提示以正式出版物为准。**不要凭空补写例句、条款或等级。**",
    )
    # 「kb-raw 只有 4 种…」这条说明在无原文层配置下整段删除
    t = re.sub(r"\n   - \*\*`kb-raw/` 只有 4 种\*\*.*?\n(?=   - |\d\. |\n)", "\n", t, flags=re.S)
    # 紧跟旧步骤的两条下探说明已无意义，删掉
    t = re.sub(
        r"   - 索引表的「行号」列是\*\*节级锚点\*\*.*?改用 `grep -n` 在正文区重新定位。\n",
        "",
        t,
        flags=re.S,
    )
    t = re.sub(r"\| `kb-raw/` \|[^\n]*\n", "", t)
    # 能力卡约束那句里并列的目录名，去掉已删除的 kb-raw
    t = re.sub(r"\s*`kb-raw/`", "", t)
    md.write_text(t, encoding="utf-8")
    changed += 1

    # overview.md 与能力卡里的 raw 指向
    for p in [staged / "overview.md", *(staged / "capabilities").glob("*.md")]:
        t = p.read_text(encoding="utf-8")
        if "kb-raw" not in t:
            continue
        t = re.sub(r"\s*→\s*`kb-raw/[^`]+`", "（条款号与要点）", t)
        t = re.sub(r"`grep -n '[^']*' \.\./kb-raw/[^`]+` 拿行号[^。]*。",
                   "在条款索引中比对规则句；需要国标示例时说明「本包未收录，以正式文本为准」。", t)
        t = t.replace("`../kb-raw/汉语拼音正词法.md`", "`../kb-index/pinyin-rules.md`")
        p.write_text(t, encoding="utf-8")
        changed += 1

    # 残留检查
    leftovers = []
    for p in staged.rglob("*.md"):
        if p.name == "PUBLICATIONS.md":
            continue
        if "kb-raw" in p.read_text(encoding="utf-8"):
            leftovers.append(str(p.relative_to(staged)))
    must(not leftovers, f"仍有 {len(leftovers)} 个文件引用已删除的 kb-raw：{leftovers[:5]}")
    return changed


# ---------- frontmatter ----------

def build_frontmatter(body: str, author: str, version: str, desc_zh: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", body, re.S)
    must(bool(m), "SKILL.md 缺少 frontmatter")
    old, rest = m.group(1), body[m.end():]

    dm = re.search(r"^description: \|\n((?:  .*\n)+)", old, re.M)
    must(bool(dm), "SKILL.md 缺少多行 description")
    desc = dm.group(1).rstrip("\n")
    meta = [l for l in old.splitlines() if l.startswith(("metadata:", "  cangjie."))]

    lines = [
        "---",
        f"name: {SLUG}",
        f"display_name: {DISPLAY_ZH}",
        f"display_name_en: {DISPLAY_EN}",
        "description: |",
        desc,
        "description_zh: |",
        *[f"  {l}" for l in desc_zh.strip().splitlines()],
        "description_en: |",
        f"  {DESC_EN}",
        "examples_zh:",
        *[f'  - "{x}"' for x in EXAMPLES_ZH],
        "examples_en:",
        *[f'  - "{x}"' for x in EXAMPLES_EN],
        f"version: {version}",
        f'author: "{author}"',
        *meta,
        "---",
        "",
    ]
    return "\n".join(lines) + rest


def check_links(staged: Path, allow_raw: bool) -> list[str]:
    pat = re.compile(r"((?:\.\./)*(?:kb-[a-z]+|capabilities)/[^\s`'\"|)\]]+?\.(?:md|tsv))")
    bad: list[str] = []
    for p in sorted(staged.rglob("*.md")):
        for m in pat.finditer(p.read_text(encoding="utf-8")):
            tgt = m.group(1)
            if "<" in tgt or "*" in tgt:
                continue
            if not allow_raw and "kb-raw/" in tgt:
                continue
            if not (p.parent / tgt).resolve().exists():
                bad.append(f"{p.relative_to(staged)} -> {tgt}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--author", required=True)
    ap.add_argument("--version", default="1.0.0")
    ap.add_argument("--desc-zh", required=True, help="详情页简介（中文），原样写入")
    ap.add_argument("--no-raw", action="store_true",
                    help="移除原文全文层（未获授权仍要公开分发时用；功能会损失三张卡的语料）")
    args = ap.parse_args()

    must((SRC / "SKILL.md").exists(), f"构建产物不存在：{SRC}（先跑 postbuild.py）")
    must((SRC / "kb-index").is_dir(), "产物不是两级布局，先跑新版 postbuild.py")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    staged = OUT_DIR / SLUG
    if staged.exists():
        shutil.rmtree(staged)
    shutil.copytree(SRC, staged)

    units = sum(1 for d in ("kb-grammar", "kb-discrimination", "kb-classroom")
                for _ in (staged / d).glob("*.md"))
    kb_dirs = [d for d in staged.iterdir() if d.is_dir() and d.name.startswith("kb-")]
    size_mb = sum(f.stat().st_size for d in kb_dirs for f in d.rglob("*") if f.is_file()) / 1024 / 1024

    if args.no_raw:
        n = drop_raw(staged)
        print(f"[no-raw] 已移除原文层，改写 {n} 个文件")

    # 出版物清单：改成本包布局的路径
    shutil.copy2(PUBLICATIONS, staged / "PUBLICATIONS.md")
    if args.no_raw:
        t = (staged / "PUBLICATIONS.md").read_text(encoding="utf-8")
        # 原文层已删：把所有指向具体原文文件的写法降级为说明文字
        t = re.sub(r"`(?:references/kb/raw/|kb-raw/)[^`]+`(\s*[、，]?\s*`[^`]+`)*", "（本包已移除）", t)
        (staged / "PUBLICATIONS.md").write_text(t, encoding="utf-8")
    apply_rules(staged / "PUBLICATIONS.md", ROOT_RULES)

    md = staged / "SKILL.md"
    md.write_text(
        build_frontmatter(md.read_text(encoding="utf-8"), args.author, args.version, args.desc_zh),
        encoding="utf-8",
    )

    broken = check_links(staged, allow_raw=True)
    must(not broken, f"{len(broken)} 处失效引用：{broken[:5]}")

    depth = max(len(p.relative_to(staged).parts) for p in staged.rglob("*") if p.is_file())
    must(depth <= 2, f"目录层级 {depth} 超过平台上限 2（二级目录/文件）")

    rc = subprocess.run(
        [sys.executable, str(CANGJIE / "scripts" / "validate_skill_pack.py"), str(staged)],
        capture_output=True, text=True, encoding="utf-8",
    )
    print("\n".join((rc.stdout or "").strip().splitlines()[-6:]))

    zpath = OUT_DIR / f"{SLUG}.zip"
    if zpath.exists():
        zpath.unlink()
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(staged.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(OUT_DIR).as_posix())

    size = zpath.stat().st_size / 1024 / 1024
    # 平台校验的是「解压后总大小」而不是压缩包大小（曾因此被拒：zip 1.52 MB / 解压 4.08 MB）
    with zipfile.ZipFile(zpath) as z:
        unpacked = sum(i.file_size for i in z.infolist() if not i.is_dir())
    LIMIT = 3145728  # 3 MB
    print(f"\n[zip] {zpath}")
    print(f"[size] 压缩 {size:.2f} MB ｜ 解压 {unpacked/1048576:.2f} MB ({unpacked} B) / 上限 3 MB —— "
          f"余量 {(LIMIT-unpacked)/1024:.0f} KB")
    print(f"[layout] 最大层级 {depth}（根/二级/文件，平台上限 2 层子目录）")
    print(f"[units] 分片 {units} 个；知识库 {size_mb:.1f} MB；原文层 {'已移除' if args.no_raw else '保留'}")
    print(f"[count] {sum(1 for p in staged.rglob('*') if p.is_file())} 个文件；author={args.author} version={args.version}")
    if rc.returncode != 0:
        print("[validate] 存在 ERROR，先修再上传")
        return 1
    return 0 if unpacked <= LIMIT else 1


if __name__ == "__main__":
    raise SystemExit(main())
