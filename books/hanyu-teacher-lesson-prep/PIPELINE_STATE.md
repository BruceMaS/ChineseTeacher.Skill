# PIPELINE_STATE — hanyu-teacher-lesson-prep

- **内容 slug**: `hanyu-teacher-lesson-prep`
- **内容标题**: 汉语教师备课知识库（11 份对外汉语教学工具书 + 国家标准合集）
- **来源**: `工具书Markdown/`（11 个 .md，约 1.83 MB）
- **目标使用目的**: 接入教师日常备课工作流
- **输出模式决策**: **single**（用户显式选择；1 个可发现入口 + 9 张内部能力卡 + 知识库层）
- **当前状态**: ✅ 全部阶段完成，已安装

## 阶段进度

| 阶段 | 状态 | 产出 |
|---|---|---|
| 0 整书理解 | 完成 | `BOOK_OVERVIEW.md` |
| 1 抽取 + 1.5 三重验证 | 完成（并入知识库构建，见下） | `kb/`（220 个知识单元） |
| 1.6 晋级门 | 不适用 | 全部 9 个能力 `destination: 未晋级`（single 模式不需要） |
| 2 RIA++ 卡片 | 完成 | `.cangjie/capabilities/cards/` 9 张 |
| 3 链接 | 完成 | `also_read` 互链 + `book/glossary.md` |
| 4 压力测试 | 完成（v1 75% → 回炉 → v2 100%） | `test-prompts.json` / `test-results.md` |
| 5 编译交付 | 完成 | `dist/hanyu-teacher-lesson-prep/` + `DIGEST.md` + 已安装 |
| 5.1 上架包 | 完成 | `dist/market/hanyu-teacher-lesson-prep.zip`（1.52 MB，**含原文层**）+ `PUBLISH.md` + `PUBLICATIONS.md` |

## 一处方法论偏离（记录在案）

cangjie 的标准链路是「原文 → 卡片」，知识只在卡片的 R 段被引用 ≤150 字。本项目的语料是**工具书**而非方法论专著：它的价值是 63 个完整教学单元、201 条辨析、571 个分级语法点这类**可检索事实**，不是 9 条可背的原则。

因此阶段 1 实际做的是**知识库抽取**而非候选提取：`scripts/build_kb.py` 把 11 份原文切成 220 个 2–8 KB 的知识单元 + 9 张索引表（`kb/`，约 5 MB），能力卡只保留方法、案例、边界、执行步骤，具体事实一律回 `kb/` 检索。

后果：`compile_single.py` 不认识 `kb/`，所以交付链路改为
`build_kb.py → cangjie compile（仅校验）→ scripts/postbuild.py（注入 kb/ + SKILL.md 知识库段 + 校验 + 原子发布）`。
**重新构建必须用 `postbuild.py`，不要直接用 `cangjie.py compile`**（后者会因 kb 路径不存在而 hard-gate 失败）。

## 关键数据

| 项 | 数量 |
|---|---|
| 语法点五段式单元 | 63 |
| 易混点辨析 | 201 |
| 课堂问题处置 | 42 |
| 国标分级语法点 | 571 |
| 国标分级词 / 字 | 11065 / 2882 |
| 拼音正词法条款 | 索引 52 条 |
| 能力卡 | 9 |
| 安装体积 | 4.9 MB / 344 个文件 |

## 已知缺陷（未修，用的时候要知道）

1. **`m2` 类分片混装多个语法点**：如 `m2-yue-lai-yue-he-yue-yue.md` 同时含「越来越」（二级 2·044）与「越…越…」（三级 3·042）；`grammar-points.md` 索引只给一个检索码，需人工拆级。
2. **国标近似匹配存在歧义**：索引对"把"字句给出"多个候选（3/4/5/6/7-9），查国标"——这是刻意保留的不确定，不是 bug（把字句确实分属五个等级）。
3. **释疑 201 例缺约 9 个条目标题**（序号不连续处），课堂技巧手册缺 8 个编号（内容并入前题）。
4. **词表与正词法标调冲突**：`vocab-levels.tsv` 标变调（`bú dà`），GB/T 16159 6.5.2 要求标原调。已写入 `pinyin-orthography.md` B 段。
5. **语音/汉字本体知识缺失**：语料本身没有，已写入 SKILL.md 判停，只能靠模型知识并标注。

## 复现命令

```bash
cd books/hanyu-teacher-lesson-prep
python scripts/build_kb.py        # 重建知识库（需 pypinyin）
python scripts/postbuild.py       # 编译 + 注入 kb + 校验 + 发布到 ../../dist/
# 安装
cp -r ../../dist/hanyu-teacher-lesson-prep ~/.workbuddy/skills/
```

## 发布版（market）说明

上架包与本地版**同源不同层**：

| | 本地安装版 | 上架 zip |
|---|---|---|
| 路径 | `~/.workbuddy/skills/hanyu-teacher-lesson-prep/` | `dist/market/hanyu-teacher-lesson-prep.zip` |
| 原文层 `kb/raw/` | 有（11 份，4.06 MB / 344 文件） | 无（0.73 MB / 334 文件） |
| 索引三层表 | 条款 + 行号 + grep 命令 | 仅「条款 / 章节」单列 |
| frontmatter | name + description | 另加 display_name/description_zh/examples/version/author 等市场字段 |
| 构建 | `scripts/postbuild.py` | `scripts/pack_market.py`（含断言，结构变动即报错） |

上架信息：author=Bruce，version=1.0.0，display_name=汉语教师备课知识库，无封面图。

**删除原文层的连带影响**（已在发布版中修补，但要知道代价）：
- 拼音条款示例、面试指南案例正文、跨文化章节正文在发布版中**不可读**，只剩条款号与章节标题；这三块的实质内容退化为能力卡内的摘要。
- 分片头部「来源 + 行号」在发布版中仅为溯源记录，无法按行号回查。
- 已修 12 处失效指引 + 3 张索引表，并在拼音卡补「GB/T 16159 未单列：隔音符号 / ü 省写 / 机构名」边界表。

**待用户决定**：版权路径 A（自用）/ B（免费上架+标注来源）/ C（收费，需授权）。见 `PUBLISH.md` 第 6 节。

## 原文层回归（2026-10-30 晚）

用户问「删掉 raw 是否影响使用」，实测确认影响严重，已把原文层加回上架包。

**影响面（4 份原文完全无切片，只剩目录）**：面试指南 263 KB、跨文化 349 KB、拼音正词法 28 KB、语法点汇总 13 KB。
对应三张能力卡失去语料支撑：`demo-lesson-shuoke`、`intercultural-framing`、`pinyin-orthography`。

**加回时修掉的两个隐藏缺陷（都是删 raw 期间被掩盖的）**：

1. 行号系统性漂移：`copy_kb()` 对 `raw/` 也删除了 OCR 页图整行，导致行号前移（语法手册 643 行、跨文化 27 行、面试 19 行）。
   修法：`strip_ocr_images(keep_lines=True)` 对 raw 保留行、只清链接。11 份文件行数与源文件逐行一致，实测三组锚点零偏差。
2. 国标 2.7 量化表丢行：`rowspan` 合并列导致 5 列续行被 `len>=6` 过滤，二/三/五/六级指标全丢。
   修法：组首记住等次、续行补齐；现一至九级 + 总计 9 行齐全。

**检索协议补充**：索引行号为「节级锚点」非内容行，命中后需在同节内下探；索引可能混入目录页条目，读到目录时改用 grep 重定位。

**上架包现状**：345 文件 / 1.52 MB（限 3 MB），11 份 raw，行号可回查，`0 errors 0 warnings`。
**版权口径变化**：含全文副本后，公开上架需授权。`PUBLISH.md` 第 6 节已给 A（自用）/ B（删 raw 免费上架）/ C（授权后上架）三条路径。

## 两级目录改造（2026-10-30 晚，平台拒绝后）

**触发**：上传报「目录层级超限 — Skill 包仅支持两级结构（根目录/二级目录/文件）」。原结构最深 4 级：
`references/kb/grammar/x.md`、`references/kb/raw/x.md`（4 级），`references/capabilities/x.md`（3 级）。

**新布局**（全部根下平级，最大 2 段）：
```
SKILL.md / capability-index.md / overview.md / glossary.md / cheatsheet.md / PUBLICATIONS.md
capabilities/  kb-index/  kb-grammar/  kb-discrimination/  kb-classroom/  kb-standards/  kb-raw/
```

**实现**（`postbuild.py` 新增三段）：
1. `flatten_tree()`：编译产物里的 `references/*` 提升到根。
2. `rewrite_refs()`：按文件位置分四组规则重写引用——根文件（`references/capabilities/`→`capabilities/`）、
   能力卡（`../kb/index/`→`../kb-index/`）、索引表（`raw/x`→`../kb-raw/x`、`index/y`→`y`）、overview（`kb/grammar/`→`kb-grammar/`）。
   本轮共改 582 处（root 29 / capabilities 24 / kb-index 513 / overview 16）。
3. `check_links()`：全量扫 `kb-*/` 与 `capabilities/` 路径（含 grep 命令里的相对路径），目标不存在即构建失败；
   另加层级 >2 即失败。**两道硬门禁**。

**`pack_market.py` 重写**：路径全部改到新布局；新增 `--no-raw`（原 `--keep-raw` 反转为默认保留）；
PUBLICATIONS.md 复制后按 `ROOT_RULES` 重写路径；补 `check_links` 与层级断言。
`--no-raw` 模式实测可用（0.72 MB / 334 文件 / 10 个文件被改写 / 无 kb-raw 残留）。

**验证**：zip 345 文件、最大层级 2、583 处引用 0 失效、`0 errors 0 warnings`、1.52 MB。
功能实测（新布局）：说课要点+文化休克原文、以前/以后/以来辨析，路径全部走通，无 BROKEN 路径；
最深访问 `kb-raw/x.md` 二级，与 SKILL.md 声明一致。

**遗留（内容层，非结构）**：`d001.md` 析疑段两张时点对比表在原书是图片，OCR 未转出表体；
`d001.md` 考考你⑦⑧题干残缺且无答案；`interview.md` 首条顺序错乱（定位无碍）。

## 减重改造（2026-10-30 晚，平台报「解压后 3259.89 KB > 3 MB」）

**诊断**：平台校验的是**解压后总字节**，不是 zip 大小（1.52 MB 的 zip 解压为 4.08 MB）。
`kb-raw/` 独占 2.53 MB，是唯一有意义的减重空间。

**判断标准**：不看"书重不重要"，看"有没有被分片覆盖"。
- 语法手册1/2（603 KB）、释疑201例1/2（378 KB）、课堂技巧手册（114 KB）：分片 = 全书 1:1 切分
  （切片汉字 139,529 vs 原文 137,263；95,104 vs 89,225；34,474 vs 32,619，差额为分片头）→ **原文冗余，删除**
- 等级标准1/2（832 KB）：主体是词汇表 545 KB + 汉字表 90 KB，已转 TSV → **原文删除**
- 面试指南、跨文化、拼音正词法、语法点汇总（667 KB）：无分片 → **保留**

**为删等级标准原文而先补的两张表**（原本只存在于原文，删了就真丢）：
- `kb-index/syllables.tsv` 1097 条（1:269 / 2:198 / 3:140 / 4-5:203 / 6:86 / 7-9:201；国标 1110，差额为去重与 OCR 噪声）
- `kb-index/handwriting.tsv` 1200 条（初等 300 / 中等 400 / 高等 500，与国标完全一致）

**顺带修的真 bug**：`char-levels.tsv` 原只有 1/2/3/7-9 级——5.4/5.5/5.6 标题在 OCR 中丢失，
5.3 抽表一路吃到 5.7，把四至六级 1084 字全标成"三级"，**超纲判定会判错**。
后重新解析该书第 24—27 页（`page24`–`page27.md`），补回三个标题并按原表拆分为三级 300 / 四级 235 /
五级 300 / 六级 250 字。再补四级 1—65、六级 1—50 两页截图后，四级、六级各补齐至 300 字，
**一至六级全部为 1—300 连续无缺的完整表**（仅 4 个跨级重复字按首次出现级别收录）。

**同步修改**：
- `build_kb.py`：`CORE_RAW` 白名单；新增 build_syllables / build_handwriting；分片头加「原书未随包，本片即该单元全文」；
  README 改写（检索协议只对 4 种可回退原文，其余用 `grep -rl` 在分片里找）；补 handwriting "查不到≠缺数据" 说明
- `postbuild.py`：KB_SECTION 同步（3 MB / 4 种 / 新增 2 张表 / 回退只限 4 种）
- `pack_market.py`：体积门禁改为**按解压后字节**判定；`--no-raw` 分支适配新文案
- `overview.md`、`PUBLICATIONS.md`、`DIGEST.md`、`PUBLISH.md` 同步

**结果**：dist 339 文件 / 2.27 MB；market zip 340 文件 / 压缩 0.99 MB / **解压 2.28 MB**，余量 736 KB（24%）；
引用 573 处 0 失效；`0 errors 0 warnings`；版本 1.0.1。`--no-raw` 模式实测 1.63 MB（余量 1404 KB）。

**验证**：功能测试四问（把字句五段式备课+12 条偏误、以前/以后/以来辨析、蘑菇/盏/zhuā/赢 四项分级、文化休克原文）
全部答对并带出处；唯一"缺口"是手写表查不到"赢/盏"——经核实为**正确结果**（该字不在会写要求内），已加说明防误答。
