# 汉语教师备课知识库（hanyu-teacher-lesson-prep）

一个面向**国际中文教师备课**的检索型知识库技能包：把 11 本国际中文教育工具书拆成可检索的索引表与分片，供 AI 在备课时落到具体语料上回答，而不是凭印象生成。

- 当前版本：**1.0.3**
- 作者：Bruce
- 适用：语法点备课、等级对标与超纲判断、偏误预测、易混词辨析、操练与课堂活动设计、说课与试讲脚本、课堂状况处置、拼音正词法、跨文化框架

## 目录结构

```
工具书Markdown/                     11 本工具书的 OCR 全文（构建输入）
books/hanyu-teacher-lesson-prep/    工程目录
  .cangjie/capabilities/            9 张能力卡 + verified.yaml + 测试用例
  scripts/                          build_kb.py / postbuild.py / pack_market.py
  kb/                               构建产出的知识库（索引表 + 分片 + 原文层）
dist/
  hanyu-teacher-lesson-prep/        可直接安装的技能包（两级目录）
  market/hanyu-teacher-lesson-prep.zip  上架用压缩包（≤3 MB 解压体积）
icon.png
```

## 安装

把 `dist/hanyu-teacher-lesson-prep/` 整个目录复制到 WorkBuddy 的用户技能目录：

```bash
cp -r dist/hanyu-teacher-lesson-prep ~/.workbuddy/skills/hanyu-teacher-lesson-prep
```

Windows 对应 `C:/Users/<用户名>/.workbuddy/skills/`。

## 从源文件重建

需要 Python 3.9+。

```bash
cd books/hanyu-teacher-lesson-prep
python scripts/build_kb.py      # 从 工具书Markdown/ 抽取知识库到 kb/
python scripts/postbuild.py     # 编译能力卡、重排两级目录、校验并发布到 dist/
python scripts/pack_market.py --author "Bruce" --version 1.0.3 \
    --desc-zh "本技能由多本国际中文教育工具书蒸馏而成，主要为汉语教师提供备课思路。"
```

注意 `postbuild.py` **不会**自动重跑 `build_kb.py`，改了源文件必须先构建知识库再发布。

## 知识库规模

| 内容 | 数量 |
|---|---|
| 语法点教学单元（五段式分片） | 63 |
| 易混词语辨析（释疑 201 例） | 201 |
| 课堂技巧问题 | 42 |
| 国标语法点（GF 0025—2021） | 571 |
| 分级词汇 | 11065 |
| 分级汉字（一至六级各 300、七至九级 1200） | 2996（4 个跨级重复字按首次出现级别收录） |
| 分级音节 | 1097 |
| 手写汉字要求 | 1200 |

## 版权说明

**本仓库包含受版权保护图书的 OCR 全文与据此切分的分片，仅限个人学习与教学参考使用，不得用于商业再分发。**

- 国家标准（GB/T 16159—2012、GF 0025—2021）属技术规范，条款号与规则内容可公开引用。
- 原文为 OCR 稿，无排版、有错字、缺图表，不能代替阅读原书。
- 出版物清单与权利状态见 `books/hanyu-teacher-lesson-prep/PUBLICATIONS.md`。
- 若权利人认为使用方式不当，请联系作者，将在核实后删除相应内容。
