#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_kb.py — 把 11 份工具书原文切分成可精确检索的知识库。

设计目标（为什么切、而不是让 agent grep 大文件）：
1. 原文单文件最大 739 KB，整读会占满上下文；切分后一次只读一个知识单元（2-8 KB）。
2. 语法手册的每个语法点都有固定五段式（知识扫描/格式/常见偏误/教学提示/教学建议），
   按"知识扫描"锚点切分可以保证一个分片 = 一个完整的教学单元，不跨点。
3. 等级标准里的 429 个语法点与 11092 个词汇做成索引表，供"对标等级/查超纲"精确命中。

用法: python build_kb.py
输出: kb/（raw/ 原文副本、grammar/ 语法点分片、discrimination/ 辨析分片、
      classroom/ 课堂技巧分片、index/ 各类索引、standards/ 国标数据）
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

SRC = Path(r"D:/个人文档/ChineseTeacher.Skill/工具书Markdown")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "kb"

F_MANUAL1 = "国际汉语教师语法教学手册1.md"
F_MANUAL2 = "国际汉语教师语法教学手册2.md"
F_DIS1 = "对外汉语教学语法释疑201例1.md"
F_DIS2 = "对外汉语教学语法释疑201例2.md"
F_CLASS = "国际汉语教师课堂技巧手册.md"
F_STD1 = "国际中文教育水平等级标准1.md"
F_STD2 = "国际中文教育水平等级标准2.md"
F_PINYIN = "汉语拼音正词法.md"
F_CROSS = "跨文化交际学概论.md"
F_INTERVIEW = "国教证书面试指南.md"
F_SUMMARY = "对外汉语教学语法点汇总.md"

CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def read(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def lines_of(name: str) -> list[str]:
    return read(name).split("\n")


def ensure(p: Path) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def slugify(text: str, maxlen: int = 40) -> str:
    """中文标题 → 拼音 slug，保留数字与字母，用于分片文件名。"""
    from pypinyin import lazy_pinyin

    text = re.sub(r"[\$\\{}^_]", "", text)
    text = re.sub(r"[（(].*?[）)]", "", text)
    parts = lazy_pinyin(text)
    s = "-".join(parts)
    s = re.sub(r"[^a-z0-9\-]+", "-", s.lower())
    s = re.sub(r"-{2,}", "-", s).strip("-")
    if len(s) > maxlen:
        s = s[:maxlen]
        if "-" in s:
            s = s[: s.rfind("-")]
    return s.strip("-") or "x"


# ---------------------------------------------------------------- 原文副本
# 只有「没有做分片」的书才需要随包带原文：其余 5 本的正文已被分片 1:1 收录，
# 2 本等级标准的可检索内容已抽成分级表，重复携带只会撑大体积（见 PIPELINE_STATE）。
CORE_RAW = (F_INTERVIEW, F_CROSS, F_PINYIN, F_SUMMARY)


def copy_raw() -> list[str]:
    dest = ensure(OUT / "raw" / "x")
    dest.parent.mkdir(parents=True, exist_ok=True)
    names = []
    for name in CORE_RAW:
        f = SRC / name
        if f.exists():
            shutil.copy2(f, dest.parent / f.name)
            names.append(f.name)
    (dest).unlink(missing_ok=True)
    return names


# ---------------------------------------------------------------- 语法手册分片
HEAD_MARK = re.compile(r"^(#{0,3})\s*(.+)$")


def is_anchor(line: str, word: str) -> bool:
    s = line.strip().lstrip("#").strip().strip("·.… ").strip()
    return s == word


# 少数语法点的标题被 OCR 吞掉或错位，用人工校订表补全（行号: 标题）
TITLE_FIX = {
    (F_MANUAL1, 12): "00 凡例：副词“也”（示例段）",
    (F_MANUAL1, 4946): "12 副词“就”和“才”",
    (F_MANUAL2, 1510): "38 “是”字句",
}


def find_title(lines: list[str], anchor: int, fname: str) -> tuple[str, int]:
    key = (fname, anchor + 1)
    if key in TITLE_FIX:
        return TITLE_FIX[key], anchor
    # 向上最多 6 行找 "# 12 副词..." 这种编号标题
    for j in range(anchor - 1, max(-1, anchor - 7), -1):
        s = lines[j].strip()
        m = re.match(r"^#{0,3}\s*(\d{1,2})\s+(\S.*)$", s)
        if m:
            return f"{m.group(1)} {m.group(2).strip()}", j
        if s and not s.startswith("#") and not s.startswith("!["):
            # 遇到正文说明已越过标题区
            if len(s) > 60:
                break
    return "", anchor


def build_grammar() -> list[dict]:
    rows: list[dict] = []
    seq = 0
    for fname, tag in ((F_MANUAL1, "m1"), (F_MANUAL2, "m2")):
        lines = lines_of(fname)
        anchors = [i for i, l in enumerate(lines) if is_anchor(l, "知识扫描")]
        # 每个语法点的起始行（标题行）
        starts = []
        for a in anchors:
            title, tline = find_title(lines, a, fname)
            starts.append((a, tline, title))
        for idx, (a, tline, title) in enumerate(starts):
            begin = min(tline, a)
            end = starts[idx + 1][1] if idx + 1 < len(starts) else len(lines)
            end = max(end, a + 1)
            body = "\n".join(lines[begin:end]).strip("\n")
            if not body:
                continue
            seq += 1
            num = title.split(" ")[0] if title else f"{seq:02d}"
            name = title.split(" ", 1)[1] if " " in title else (title or "未命名语法点")
            slug = f"{tag}-{slugify(name) or seq}"
            path = OUT / "grammar" / f"{slug}.md"
            # 知识扫描首句作为一句话核心
            seg = lines[a:end]
            first = ""
            for l in seg[1:]:
                s = l.strip()
                if s and not s.startswith(("#", "!", "格式", "$")):
                    first = re.sub(r"\s+", "", s)
                    break
            has_err = any(("常见偏误" in l or "常见偏程" in l) for l in seg)
            has_teach = any("教学建议" in l for l in seg)
            n_case = sum(1 for l in seg if re.match(r"^#{1,3}\s*案例", l.strip()))
            ensure(path).write_text(
                f"""# {num} {name}

> 来源：`{fname}` 第 {begin + 1}–{end} 行（五段式：知识扫描 / 格式 / 常见偏误 / 教学提示 / 教学建议；原书未随包，本片即该单元全文）
> 检索码：`{slug}`

{body}
""",
                encoding="utf-8",
            )
            rows.append(
                {
                    "num": num,
                    "name": name,
                    "slug": slug,
                    "src": fname,
                    "line": begin + 1,
                    "first": first[:70],
                    "err": has_err,
                    "teach": has_teach,
                    "case": n_case,
                }
            )
    return rows


# ---------------------------------------------------------------- 释疑 201 例
def build_discrimination() -> list[dict]:
    rows: list[dict] = []
    heads_all: list[tuple[str, int, int, str]] = []
    for fname in (F_DIS1, F_DIS2):
        lines = lines_of(fname)
        heads = []
        for i, l in enumerate(lines):
            m = re.match(r"^#{1,3}\s*(\d{1,3})\s*[.、．]\s*(.+)$", l.strip())
            if m and 1 <= int(m.group(1)) <= 201:
                heads.append((i, int(m.group(1)), m.group(2).strip()))
        heads_all.append((fname, heads))
    found = {h[1] for _, hs in heads_all for h in hs}
    # 少数条目在 OCR 中丢失了 ## 标题，退化为正文行：按序号在原文定位补齐
    for missing in sorted(set(range(1, 202)) - found):
        for fname in (F_DIS1, F_DIS2):
            lines = lines_of(fname)
            for i, l in enumerate(lines):
                s = l.strip()
                if re.match(rf"^{missing}[.、．]\s*\S", s) and len(s) < 60:
                    title = re.sub(rf"^{missing}[.、．]\s*", "", s).strip(" 。")
                    heads_all[[n for n, _ in heads_all].index(fname)][1].append((i, missing, title))
                    found.add(missing)
                    break
            if missing in found:
                break
    for fname, heads in heads_all:
        heads.sort(key=lambda x: x[0])
        lines = lines_of(fname)
        for k, (i, num, title) in enumerate(heads):
            end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
            body = "\n".join(lines[i:end]).strip("\n")
            slug = f"d{num:03d}"
            ensure(OUT / "discrimination" / f"{slug}.md").write_text(
                f"""# {num} {title}

> 来源：`{fname}` 第 {i + 1}–{end} 行（结构：疑问 / 析疑 / 考考你；原书未随包，本片即该条全文）

{body}
""",
                encoding="utf-8",
            )
            rows.append({"num": num, "title": title, "slug": slug, "src": fname, "line": i + 1})
    rows.sort(key=lambda r: r["num"])
    return rows


# ---------------------------------------------------------------- 课堂技巧
def build_classroom() -> list[dict]:
    fname = F_CLASS
    lines = lines_of(fname)
    heads = []
    for i, l in enumerate(lines):
        m = re.match(r"^#{1,3}\s*(\d{1,3})\s*[.、．]\s*(.+)$", l.strip())
        if m and "？" in m.group(2) or (m and "?" in m.group(2)):
            heads.append((i, m.group(1), m.group(2).strip()))
    rows: list[dict] = []
    for k, (i, num, title) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        body = "\n".join(lines[i:end]).strip("\n")
        slug = f"c{int(num):02d}"
        ensure(OUT / "classroom" / f"{slug}.md").write_text(
            f"""# {num}. {title}

> 来源：`{fname}` 第 {i + 1}–{end} 行（结构：思考问题 / 编者信箱 / 分点作答；原书未随包，本片即该问全文）

{body}
""",
            encoding="utf-8",
        )
        rows.append({"num": num, "title": title, "slug": slug, "line": i + 1})
    return rows


# ---------------------------------------------------------------- 等级标准
CELL = "\x01"


def table_rows(block: str) -> list[list[str]]:
    out = []
    for tr in re.findall(r"<tr>(.*?)</tr>", block, flags=re.S):
        s = re.sub(r"</td>", CELL, tr)
        s = re.sub(r"<td[^>]*>", "", s)
        s = re.sub(r"<[^>]+>", "", s)
        cells = [c.strip() for c in s.split(CELL)]
        cells = [c for c in cells if c]
        if cells:
            out.append(cells)
    return out


def section_bounds(text: str, start_pat: str, end_pat: str) -> tuple[int, int] | None:
    m = re.search(start_pat, text)
    if not m:
        return None
    e = re.search(end_pat, text[m.end():])
    return m.end(), (m.end() + e.start() if e else len(text))


def build_vocab() -> list[tuple[str, int, str]]:
    text = read(F_STD1)
    out = []
    for sec, lvl in (
        ("## 6.1 一级词汇表", 1),
        ("## 6.2 二级词汇表", 2),
        ("## 6.3 三级词汇表", 3),
        ("## 6.4 四级词汇表", 4),
        ("## 6.5 五级词汇表", 5),
        ("## 6.6 六级词汇表", 6),
    ):
        b = section_bounds(text, re.escape(sec), r"\n## ")
        if not b:
            continue
        for cells in table_rows(text[b[0]:b[1]]):
            # (num, word, pinyin) 重复
            i = 0
            while i + 2 < len(cells) + 1 and i + 2 <= len(cells):
                if re.fullmatch(r"\d+", cells[i]) and i + 2 < len(cells) + 1:
                    if i + 2 >= len(cells) + 1:
                        break
                    word = cells[i + 1] if i + 1 < len(cells) else ""
                    pin = cells[i + 2] if i + 2 < len(cells) else ""
                    if word and not re.fullmatch(r"[a-zA-Zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü\s]+", word):
                        out.append((word, lvl, pin))
                    i += 3
                else:
                    i += 1
    b = section_bounds(text, re.escape("## 6.7 七一九级词汇表"), r"\n## |\Z")
    if b:
        for cells in table_rows(text[b[0]:b[1]]):
            i = 0
            while i + 2 <= len(cells):
                if re.fullmatch(r"\d+", cells[i]) and i + 2 < len(cells):
                    word = cells[i + 1]
                    if word and not re.fullmatch(r"[a-zA-Zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü\s]+", word):
                        out.append((word, 79, cells[i + 2]))
                    i += 3
                else:
                    i += 1
    return out


def _tables_between(start: str, end: str, text: str | None = None) -> list[str]:
    """取 start 标题之后、end 之前的所有 <table> 块（用于标题被 OCR 吞掉的分级表）。"""
    t = text if text is not None else read(F_STD1)
    m = re.search(re.escape(start), t)
    if not m:
        return []
    e = re.search(end, t[m.end():])
    seg = t[m.end(): m.end() + e.start()] if e else t[m.end():]
    return re.findall(r"<table>.*?</table>", seg, flags=re.S)


def _pairs(block: str) -> list[str]:
    """表内每行是「序号 值 序号 值 …」，去掉纯数字序号只留值。"""
    out: list[str] = []
    for tr in re.findall(r"<tr>(.*?)</tr>", block, flags=re.S):
        for c in re.findall(r"<td>([^<]*)</td>", tr):
            c = c.strip()
            if c and not re.fullmatch(r"\d+", c):
                out.append(c)
    return out


# 标题存在且可用的音节表分节；4.4 一块实际含四级+五级（5.x 同类标题被 OCR 吞掉）
SYLLABLE_SECS = (
    ("## 4.1 一级音节表", r"\n## 4\.2", "1"),
    ("## 4.2 二级音节表", r"\n## 4\.3", "2"),
    ("## 4.3 三级音节表", r"\n## 4\.4", "3"),
    ("## 4.4 四级音节表", r"\n## 4\.6", "4-5"),
    ("## 4.6 六级音节表", r"\n## 4\.7", "6"),
    ("## 4.7 七一九级音节表", r"\n## 5 汉字表", "7-9"),
)


def build_syllables() -> list[tuple[str, str]]:
    text = read(F_STD1)
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for sec, end, lvl in SYLLABLE_SECS:
        for blk in _tables_between(sec, end, text):
            for v in _pairs(blk):
                if re.fullmatch(r"[a-zA-Zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüêńňǹḿ\s]+", v) and v not in seen:
                    seen.add(v)
                    out.append((v, lvl))
    return out


def build_handwriting() -> list[tuple[str, str]]:
    """手写汉字表 5.8：初等/中等/高等三档。5.8.2 标题被 OCR 吞掉，按表格块顺序归组。"""
    blocks = _tables_between("## 5.8 手写汉字表", r"\n## 6 词汇表")
    out: list[tuple[str, str]] = []
    for i, blk in enumerate(blocks):
        band = "初等" if i <= 1 else ("中等" if i == 2 else "高等")
        for v in _pairs(blk):
            if re.fullmatch(r"[\u4e00-\u9fff]{1,3}", v):
                for ch in v:
                    out.append((ch, band))
    return out


def build_chars() -> list[tuple[str, str]]:
    """汉字表 5.1–5.7，每级一张表（一至六级各 300 字，七至九级 1200 字，共 3000 项）。

    原书 5.4/5.5/5.6 三个小标题曾被 OCR 吞掉，字表并入 5.3 且序号乱码；已用重解析的分页
    表格补回标题与数据，并补齐四级第 1—65 字、六级第 1—50 字这两处缺页，现六级各表
    编号 1—300 连续无缺。跨级重复字按「首次出现的级别」收录（兵、江、竞 计四级，卤 计七至九级）。"""
    text = read(F_STD1)
    out = []
    for sec, lvl in (
        ("## 5.1 一级汉字表", "1"),
        ("## 5.2 二级汉字表", "2"),
        ("## 5.3 三级汉字表", "3"),
        ("## 5.4 四级汉字表", "4"),
        ("## 5.5 五级汉字表", "5"),
        ("## 5.6 六级汉字表", "6"),
        ("## 5.7 七一九级汉字表", "7-9"),
    ):
        b = section_bounds(text, re.escape(sec), r"\n## ")
        if not b:
            continue
        for cells in table_rows(text[b[0]:b[1]]):
            i = 0
            while i + 1 < len(cells):
                if re.fullmatch(r"\d+", cells[i]) and re.fullmatch(r"[\u4e00-\u9fff]{1,3}", cells[i + 1]):
                    for ch in cells[i + 1]:
                        out.append((ch, lvl))
                    i += 2
                else:
                    i += 1
    return out


def parse_level_tag(tag: str) -> tuple[str, int]:
    """从「一05」「三 19」「七—九 002」「七一九004」解析出等级与编号。"""
    m = re.match(r"([一二三四五六七八九])", tag)
    if not m:
        return "0", 0
    a = CN_NUM[m.group(1)]
    rest = tag[m.end():]
    level = str(a)
    if a in (7, 8, 9) and "九" in rest:
        level = "7-9"
    num = re.search(r"(\d{1,3})\s*$", tag)
    return level, int(num.group(1)) if num else 0


def build_grammar_levels() -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for fname in (F_STD1, F_STD2):
        lines = lines_of(fname)
        cur_cat = ""
        cur_sub = ""
        for i, l in enumerate(lines):
            s = l.strip()
            mcat = re.match(r"^#{1,3}\s*(A\.\d+\.\d+(?:\.\d+)?)\s*(.+)$", s)
            if mcat:
                cur_cat = f"{mcat.group(1)} {mcat.group(2).strip()}"
                cur_sub = ""
                continue
            msub = re.match(r"^#{1,3}\s*A\.\d+(?:\.\d+)*\.\d+\s*(.+)$", s)
            if msub:
                cur_sub = msub.group(1).strip()
                continue
            m = re.match(r"^(?:#{1,4}\s*)?【(.{1,10}?)】\s*(.+)$", s)
            if not m:
                continue
            level, num = parse_level_tag(m.group(1))
            if not level or level == "0":
                continue
            code = f"{level}·{num:03d}"
            if code in seen:  # 同一语法点在正文中被再次引用，只保留首次（定义处）
                continue
            seen.add(code)
            name = m.group(2).strip()
            ex = ""
            for k in range(i + 1, min(i + 14, len(lines))):
                t = lines[k].strip()
                if t and not t.startswith(("#", "!", "|", "【", "GF ")) and not re.fullmatch(r"\d+", t):
                    ex = t
                    break
            rows.append(
                {
                    "level": level,
                    "code": f"{level}·{num:03d}",
                    "name": name,
                    "cat": cur_cat,
                    "sub": cur_sub,
                    "example": ex,
                    "src": fname,
                    "line": i + 1,
                }
            )
    return rows


def build_level_descriptors() -> str:
    text = read(F_STD1)
    b = section_bounds(text, re.escape("## 3 等级描述"), r"\n## 4 音节表")
    body = text[b[0]:b[1]] if b else ""
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def build_quant() -> str:
    text = read(F_STD1)
    b = section_bounds(text, re.escape("## 2.7"), r"\n## 3 等级描述")
    block = text[b[0]:b[1]] if b else ""
    rows = table_rows(block)
    out = ["# 语言量化指标总表（音节/汉字/词汇/语法点累计）", "", "| 等次 | 级别 | 音节 | 汉字 | 词汇 | 语法点 |", "|---|---|---|---|---|---|"]

    # 原书表格用 rowspan 合并「等次」列，解析后该列只在组首出现，后续行为 5 列。
    # 处理：组首行记住等次，5 列行补齐等次；表头重复行与表注行跳过。
    cur_band = ""
    for r in rows:
        if not r:
            continue
        if r[0] in ("等次", "等 次"):          # 重复表头
            continue
        if len(r) < 5:                          # 表注
            continue
        if len(r) >= 6:                         # 组首行：等次 + 级别 + 4 项指标
            cur_band = r[0]
            out.append("| " + " | ".join(r[:6]) + " |")
        else:                                   # 续行：级别 + 4 项指标
            band = "全部等次" if r[0] == "总计" else cur_band
            out.append("| " + " | ".join([band] + r[:5]) + " |")

    out.append("")
    out.append("> 格式为「本级新增/累计」。来源：GF 0025—2021 第 2.7 节。高等不按级细分。")
    return "\n".join(out)


# ---------------------------------------------------------------- 其它索引
def line_index(fname: str, patterns: list[str], title: str, note: str = "") -> str:
    lines = lines_of(fname)
    out = [f"# {title}", "", note, "", "| 条款/标题 | 行号 | 检索 |", "|---|---|---|"]
    for i, l in enumerate(lines):
        s = l.strip()
        for p in patterns:
            m = re.match(p, s)
            if m:
                label = s.lstrip("# ").strip()
                out.append(f"| {label} | {i + 1} | `grep -n '{label[:12]}' raw/{fname}` |")
                break
    return "\n".join(out)


def build_pinyin_index() -> str:
    return line_index(
        F_PINYIN,
        [r"^#{1,3}\s*5\.\d+", r"^#{1,3}\s*6\.\d+(\.\d+)*\s", r"^#{1,3}\s*7\."],
        "汉语拼音正词法（GB/T 16159—2012）条款索引",
        "国标条款，可直接引用条款号作为依据。",
    )


def build_cross_index() -> str:
    return line_index(
        F_CROSS,
        [r"^#{1,3}\s*第.{1,3}章", r"^#{1,3}\s*[一二三四五六七八九十]+、"],
        "跨文化交际学概论 章节索引",
        "用于校准术语与框架；具体课堂应对以模型自身知识为主。",
    )


def build_interview_index() -> str:
    base = line_index(
        F_INTERVIEW,
        [r"^#{1,3}\s*[一二三四五六七八九十]+、", r"^#{1,3}\s*（[一二三四五六七八九十]+）", r"^#{1,3}\s*\d+\.\s"],
        "《国际汉语教师证书》面试指南 结构索引",
        "说课四要点、试讲脚本、中文/外语问答范式。",
    )
    extra = """

## 案例分析方法（中文问答/课堂困境通用）

| 案例类型 | 分析步骤 | 出处 |
|---|---|---|
| 以解决问题为导向（还没结果） | 分析原因 → 解决方案 → 利弊评析 | `raw/国教证书面试指南.md` 第 2027–2050 行 |
| 以结果为导向（已有结果） | 关键问题 → 处理方案 → 合理建议 → 行动方案 | 同上 第 2040–2050 行 |

## 案例库分区（按行号读原文）

| 领域 | 起始行 |
|---|---|
| 教学组织与课堂管理 | 2053 |
| 中华文化与跨文化交际 | 2145 |
| 职业道德与专业发展 | 2203 |
| 案例库（三个领域合集） | 2263 起 |

> 用法：先确定案例属于哪个领域、哪一类（有无既有结果），再套对应步骤；读原文时按行号读 ±120 行。
"""
    return base + extra


def build_summary_index() -> str:
    fname = F_SUMMARY
    lines = lines_of(fname)
    out = ["# 对外汉语教学基本语法 40 项（覆盖度校验表）", "", "> 用于检查备课是否遗漏必备项目。原文见 `raw/" + fname + "`。", ""]
    for i, l in enumerate(lines):
        s = l.strip()
        m = re.match(r"^(\d{1,2})[.、]\s*(.+)$", s)
        if m:
            out.append(f"- [{m.group(1)}] {m.group(2)}（第 {i + 1} 行）")
    out.append("")
    out.append("## 句法框架（原文开篇）")
    out.append("")
    out.extend(lines[1:14])
    return "\n".join(out)


# ---------------------------------------------------------------- 写索引
def clean_name(s: str) -> str:
    s = re.sub(r"\$[^$]*\$", "", s)
    s = re.sub(r"\^\{[^}]*\}", "", s)
    s = re.sub(r"[①②③④⑤⑥⑦⑧⑨]", "", s)
    s = re.sub(r"[（(][^）)]*[）)]", "", s)
    s = re.sub(r"[“”\"'‘’：:、，,。．.\s\-—…]", "", s)
    s = re.sub(r"\d+", "", s)
    return s


def write_grammar_index(rows: list[dict], glv: list[dict]) -> None:
    out = [
        f"# 语法点分片索引（{len(rows)} 个教学单元，含 1 段凡例）",
        "",
        "> 语料：国际汉语教师语法教学手册 1/2。每个分片 = 一个完整五段式教学单元。",
        "> 用法：先在本表按名称/关键词定位 → 读 `grammar/<检索码>.md` → 等级另查 `grammar-levels.md`。",
        "> **末列只标注「唯一可判定」的国标等级；显示「查国标」时必须去 `grammar-levels.md` 核实，不得凭感觉定级。**",
        "",
        "| # | 名称 | 检索码 | 偏误段 | 教学案例 | 国标等级 |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        key = clean_name(r["name"])
        hits = [g for g in glv if key and key in clean_name(g["name"])]
        levels = {h["level"] for h in hits}
        if len(hits) == 1:
            lv = hits[0]
            tag = f"{lv['level']} 级 · {lv['name'][:26]}"
        elif len(hits) > 1 and len(levels) == 1:
            tag = f"{hits[0]['level']} 级（{len(hits)} 条同义条目）"
        elif len(hits) > 1:
            tag = f"— 多个候选（{sorted(levels)}），查国标"
        else:
            tag = "— 查国标"
        out.append(
            f"| {r['num']} | {r['name']} | `grammar/{r['slug']}.md` | {'有' if r['err'] else '—'} | "
            f"{r['case']} 个 | {tag} |"
        )
    ensure(OUT / "index" / "grammar-points.md").write_text("\n".join(out) + "\n", encoding="utf-8")


def write_grammar_level_index(rows: list[dict]) -> None:
    out = [
        "# 国标语法等级大纲索引（429 个语法点，一至六级）",
        "",
        "> 来源：GF 0025—2021 附录 A《语法等级大纲》。**这是等级判断的唯一权威依据。**",
        "> 七至九级不设逐条语法点清单，按语篇与修辞能力描述（见 `level-descriptors.md`）。",
        "> 用法：`grep '把' grammar-levels.md` 定位条目 → 看「等级/编号」列判断超纲；本表即等级判定依据，不需要原文。",
        "",
        "| 级 | 编号 | 语法点 | 大类 | 细类 | 原例 | 出处行 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda x: (x["level"], x["code"])):
        ex = r["example"].replace("|", "／")[:36]
        out.append(
            f"| {r['level']} | {r['code']} | {r['name']} | {r['cat'][:20]} | {r['sub'][:12]} | {ex} | "
            f"`{r['src']}:{r['line']}` |"
        )
    ensure(OUT / "index" / "grammar-levels.md").write_text("\n".join(out) + "\n", encoding="utf-8")


def write_vocab_tsv(vocab: list[tuple[str, int, str]]) -> None:
    p = ensure(OUT / "index" / "vocab-levels.tsv")
    with p.open("w", encoding="utf-8") as f:
        f.write("词语\t级别\t拼音\n")
        for w, lv, pin in vocab:
            f.write(f"{w}\t{'7-9' if lv == 79 else lv}\t{pin}\n")


def write_char_tsv(chars: list[tuple[str, str]]) -> None:
    seen: dict[str, str] = {}
    for ch, lv in chars:
        seen.setdefault(ch, lv)
    p = ensure(OUT / "index" / "char-levels.tsv")
    with p.open("w", encoding="utf-8") as f:
        f.write("汉字\t级别\n")
        for ch, lv in seen.items():
            f.write(f"{ch}\t{lv}\n")


def write_syllable_tsv(rows: list[tuple[str, str]]) -> None:
    p = ensure(OUT / "index" / "syllables.tsv")
    with p.open("w", encoding="utf-8") as f:
        f.write("音节\t级别\n")
        for s, lv in rows:
            f.write(f"{s}\t{lv}\n")


def write_handwriting_tsv(rows: list[tuple[str, str]]) -> None:
    seen: dict[str, str] = {}
    for ch, band in rows:
        seen.setdefault(ch, band)
    p = ensure(OUT / "index" / "handwriting.tsv")
    with p.open("w", encoding="utf-8") as f:
        f.write("汉字\t等次\n")
        for ch, band in seen.items():
            f.write(f"{ch}\t{band}\n")


def write_disc_index(rows: list[dict]) -> None:
    out = [
        "# 易混词语辨析索引（释疑 201 例，实收 %d 条）" % len(rows),
        "",
        "> 来源：对外汉语教学语法释疑 201 例 1/2。每条 = 疑问（学生真实困惑）→ 析疑（区分标准）→ 考考你（检验题）。",
        "> 用法：学生问「A 和 B 有什么区别」时，按 A 或 B 在本表检索 → 读 `discrimination/<检索码>.md`。",
        "> 注意：OCR 缺失约 9 条，序号不连续处即缺条；缺条时用 `grep -rl '疑问关键词' discrimination/` 在分片里找。",
        "",
        "| 序号 | 辨析条目 | 检索码 | 出处行 |",
        "|---|---|---|---|",
    ]
    for r in rows:
        out.append(f"| {r['num']} | {r['title']} | `discrimination/{r['slug']}.md` | `{r['src']}:{r['line']}` |")
    ensure(OUT / "index" / "discrimination.md").write_text("\n".join(out) + "\n", encoding="utf-8")


def write_class_index(rows: list[dict]) -> None:
    out = [
        "# 课堂技巧索引（实收 %d 条真实课堂问题）" % len(rows),
        "",
        "> 来源：国际汉语教师课堂技巧手册。每条 = 思考问题（情境判断）→ 编者信箱（原理）→ 分点做法。",
        "> 用法：教师描述课堂困境时，按关键词检索本表 → 读 `classroom/<检索码>.md`。",
        "",
        "| 序号 | 问题 | 检索码 | 出处行 |",
        "|---|---|---|---|",
    ]
    for r in rows:
        out.append(f"| {r['num']} | {r['title']} | `classroom/{r['slug']}.md` | `{r['line']}` |")
    ensure(OUT / "index" / "classroom.md").write_text("\n".join(out) + "\n", encoding="utf-8")


def write_readme(raw_names: list[str], n_gram: int, n_dis: int, n_class: int,
                 n_vocab: int, n_char: int, n_syll: int, n_hand: int) -> None:
    out = f"""# 知识库使用协议（agent 必读）

本目录是 11 份对外汉语教学工具书蒸馏出的**可检索知识库**：正文按教学单元切成 306 个分片（每片 2–8 KB），
分级字词表另存为 TSV。原文只随包携带**没有做分片**的 4 种（面试指南、跨文化、拼音正词法、语法点汇总）；
其余 5 种教材的正文已 1:1 收入分片，等级标准的可检索内容已抽成分级表，**不必也不应再找它们的原文**。
**任何情况下都不要整目录读取或整文件通读。**

## 检索协议（按顺序执行，命中即停）

1. **先查索引，不查原文。** 索引表都在本目录（`kb-index/`），每个条目自带检索码或行号。
2. **按检索码读分片。** `grammar/` `discrimination/` `classroom/` 下每个文件是一个完整知识单元（2–8 KB），读一个就够回答一个问题。
3. **命不中才回退原文。** 只有 `raw/` 下这 4 种可回退：汉语拼音正词法、跨文化交际学概论、国教证书面试指南、对外汉语教学语法点汇总。
   用 `grep -n '关键词' raw/<文件>` 拿行号，再按行号读该行附近 ±80 行。禁止 `cat` 整个 raw 文件。
   - 语法手册、释疑 201 例、课堂技巧手册**没有随包原文**：这两类内容已在分片里，改用 `grep -rl '关键词' grammar/`（或 `discrimination/`、`classroom/`）定位分片。
   - 索引表的「行号」是**节级锚点**（节标题行），不是内容行：±80 行内没有正文时，在同一节内继续下探到下一个同级标题为止。
   - 索引表可能混入目录页条目（行号指向目录而非正文），读到目录时改用 `grep -n` 在正文区重新定位。
4. **引用要带出处。** 每个分片头部都有「来源：文件 + 行号」，回答时保留。

## 分层结构

| 目录 | 内容 | 数量 | 什么时候用 |
|---|---|---|---|
| `index/grammar-points.md` | 语法点教学单元索引（63 个单元） | 63 | 备语法点课的第一站 |
| `grammar/` | 语法点分片（五段式：知识扫描/格式/常见偏误/教学提示/教学建议） | {n_gram} | 要解释、要预判偏误、要教学脚本 |
| `index/grammar-levels.md` | 国标语法等级大纲 | 571 | 判断语法点属于几级 |
| `index/vocab-levels.tsv` | 词汇分级表（词/级/拼音） | {n_vocab} | 查某词是否超纲 |
| `index/char-levels.tsv` | 汉字分级表（一至六级各 300 字、七至九级 1200 字，编号连续无缺页） | {n_char} | 查某字是否超纲 |
| `index/syllables.tsv` | 音节分级表（一至七九级） | {n_syll} | 查某音节属几级、定语音教学范围 |
| `index/handwriting.tsv` | 手写汉字表（初等/中等/高等） | {n_hand} | 定"哪些字要求会写" |
| `standards/level-descriptors.md` | 一至九级能力描述（听说读写译） | 9 | 定教学目标和难度 |
| `standards/quantitative.md` | 音节/汉字/词汇/语法点量化指标 | — | 量化"这个班该会多少" |
| `index/discrimination.md` | 易混词辨析索引 | {n_dis} | 学生问"A 和 B 区别" |
| `discrimination/` | 辨析分片（疑问→析疑→考考你） | {n_dis} | 要给区分标准和检验题 |
| `index/classroom.md` | 课堂技巧索引 | {n_class} | 课堂出状况、教材选择、备课流程 |
| `classroom/` | 课堂技巧分片 | {n_class} | 要具体处置方案 |
| `raw/汉语拼音正词法.md` | GB/T 16159—2012 全文 | 1 | 拼音书写判定（条款号可引用） |
| `index/pinyin-rules.md` | 正词法条款索引 | — | 快速定位条款 |
| `raw/跨文化交际学概论.md` | 跨文化框架（12 章） | 1 | 校准术语（文化休克/价值观/非语言） |
| `index/cross-culture.md` | 跨文化章节索引 | — | 定位 |
| `raw/国教证书面试指南.md` | 说课/试讲/问答范式 | 1 | 说课试讲场景 |
| `index/interview.md` | 面试指南结构索引 | — | 定位 |
| `raw/对外汉语教学语法点汇总.md` | 基本语法 40 项 | 1 | 覆盖度校验 |
| `index/grammar-40.md` | 基本语法 40 项清单 | 40 | 覆盖度校验 |

## 原文层（只含 4 种，均无分片）

{chr(10).join('- `raw/' + n + '`' for n in raw_names)}

其余 7 种（语法手册 1/2、释疑 201 例 1/2、课堂技巧手册、等级标准 1/2）**不随包分发**：
前 5 种的正文即分片正文；等级标准已抽成 `index/` 下的四张分级表与 `standards/` 的两份摘要。

## 质量警告（引用前必看）

- 语法手册与释疑 201 例为扫描 OCR，存在识别错误：`常见偏程` = 常见偏误；少数标题被吞，已人工补全 3 处。
- 释疑 201 例缺约 9 个条目标题，序号不连续处即缺条。
- 课堂技巧手册原有 50 问，OCR 丢失 8 个编号（11、12、21、31、32、41、42 及末条），这些题目已并入前一题的正文，内容未丢但无法按编号精确定位。
- 等级标准的语法大纲实收 571 个语法点（一至六级 423 个 + 七至九级 148 个），四级比量化指标少 1 条（OCR 缺 1）。
- **汉字表**：原书 5.4/5.5/5.6 三个小标题曾被 OCR 吞掉，已用重解析的分页表格补回，四级、五级、六级各自成表。
  缺页（原四级第 1—65 字、六级第 1—50 字）也已补齐，**一至六级各 300 字、七至九级 1200 字，编号 1—300/1—1200 连续无缺**，
  可直接据此判定超纲与否。注意跨级重复字（兵、江、竞、卤）按首次出现的级别收录，查得级别即最低要求级别。
- **音节表**：4.5 五级标题丢失，四、五级合并标注为 `4-5`；个别音节因 OCR 重复计数，总数为 1130（标准值 1110）。
- **手写汉字表**：5.8.2 中等标题丢失，已按表格块顺序归组（初等 300 / 中等 400 / 高等 500）。
  `handwriting.tsv` 只收「要求会写」的 1200 字，**查不到不等于缺数据，而表示该字不在会写要求范围内**，回答时应说「该字不在手写汉字表内」，不要答成「本库未收录」。
- 跨文化教材成书较早，案例偏西方语境。
"""
    ensure(OUT / "index" / "README.md").write_text(out, encoding="utf-8")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    raw_names = copy_raw()
    gram = build_grammar()
    dis = build_discrimination()
    cls = build_classroom()
    glv = build_grammar_levels()
    vocab = build_vocab()
    chars = build_chars()
    sylls = build_syllables()
    hands = build_handwriting()

    ensure(OUT / "standards" / "level-descriptors.md").write_text(
        "# 等级描述（一至九级，听说读写译）\n\n> 来源：GF 0025—2021 第 3 章。用于判定教学对象等级、设定教学目标上限。\n\n"
        + build_level_descriptors()
        + "\n",
        encoding="utf-8",
    )
    ensure(OUT / "standards" / "quantitative.md").write_text(build_quant() + "\n", encoding="utf-8")

    write_grammar_index(gram, glv)
    write_grammar_level_index(glv)
    write_vocab_tsv(vocab)
    write_char_tsv(chars)
    write_syllable_tsv(sylls)
    write_handwriting_tsv(hands)
    write_disc_index(dis)
    write_class_index(cls)
    ensure(OUT / "index" / "pinyin-rules.md").write_text(build_pinyin_index() + "\n", encoding="utf-8")
    ensure(OUT / "index" / "cross-culture.md").write_text(build_cross_index() + "\n", encoding="utf-8")
    ensure(OUT / "index" / "interview.md").write_text(build_interview_index() + "\n", encoding="utf-8")
    ensure(OUT / "index" / "grammar-40.md").write_text(build_summary_index() + "\n", encoding="utf-8")
    write_readme(raw_names, len(gram), len(dis), len(cls),
                 len(vocab), len(set(c for c, _ in chars)), len(sylls), len(set(c for c, _ in hands)))

    print(f"语法点分片: {len(gram)}")
    print(f"辨析分片: {len(dis)}")
    print(f"课堂技巧分片: {len(cls)}")
    print(f"国标语法点: {len(glv)}")
    print(f"词汇: {len(vocab)}")
    print(f"汉字: {len(set(c for c, _ in chars))}")
    print(f"音节: {len(sylls)}  手写汉字: {len(set(c for c, _ in hands))}")
    print("未取到标题的语法点:", [r["name"] for r in gram if r["name"] in ("", "未命名语法点")])


if __name__ == "__main__":
    main()
