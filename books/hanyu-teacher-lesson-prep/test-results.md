# 压力测试结果 — hanyu-teacher-lesson-prep

**方法**：独立 sub-agent 盲测（非主流程自测）。给 sub-agent 的只有：skill 目录路径、SKILL.md 与 capability-index.md 的读取权限、用户 prompt 原文。**不给** `type` / `expected_behavior` / `expected_card` / 通过标准。主流程事后判卷。
**判分维度**：① 是否激活（trigger / no_trigger）② 激活后路由到哪张卡。

---

## v1（2026-02-10，8 张卡）

| 用例 | 期望 | 实测 | 结果 |
|---|---|---|---|
| p01 备课「把」字句 | trigger / grammar-point-lesson-design | 一致 | ✅ |
| p02 以前-以后辨析 | trigger / confusable-discrimination | 一致 | ✅ |
| p03 几级 / 超纲 | trigger / level-scoping | 一致 | ✅ |
| p04 说课试讲 | trigger / demo-lesson-shuoke | 一致 | ✅ |
| p05 学生不开口（日本） | trigger / classroom-diagnosis | 一致 | ✅ |
| p06 拼音连写/隔音符号 | trigger / 拼音路径 | trigger，但路由表**无卡可指向**，落回 kb | ⚠️ 结构缺口 |
| p07 简历翻译 | no_trigger | no_trigger | ✅ |
| p08 生成语法分析 | no_trigger | no_trigger | ✅ |
| p09 学生自学提问 | no_trigger | no_trigger | ✅ |
| p10 ü 省写怎么讲 | trigger + 标注非本库 | trigger，但把省写规则**误判为**正词法范围 | ❌ 边界失守 |
| p11 整学期大纲 | trigger + 降级为单元级 | **no_trigger**（按判停直接拒答） | ❌ 判停过硬 |
| p12 只盯前排 | trigger / classroom-diagnosis | 一致 | ✅ |

**通过率 9/12 = 75% → 低于 80%，按方法论必须回炉阶段 2。**

失败归因（不是修 description 就能解决的）：

1. **p06 暴露真实结构缺口**：entry description 承诺"判定拼音连写与大写"，但 8 张卡里没有拼音卡，路由表指向空气。→ 补第 9 张能力卡 `pinyin-orthography`（P7 单元在阶段 0 已预判，当时遗漏）。
2. **p10 是边界没写清**：GB/T 16159 只规管正词法（连写/大写/标调/移行），`ü` 在 j q x 后的省写属《汉语拼音方案》与语音本体。卡的 B 段没有这条分界，agent 就把两者混为一谈。→ 新卡 B 段显式列出"正词法 ≠ 拼写方案 ≠ 语音本体"。
3. **p11 是判停措辞过硬**：原文"说明超出范围，只能给单课或单元级设计"读起来像"拒答"。→ 改为"仍用量化指标给单元级骨架与周次分配，但说明整学期需校本方案，不要直接拒答"。

## v2（补卡 + 改判停后重测）

| 用例 | 期望 | 实测 | 结果 |
|---|---|---|---|
| p01–p05 | 同 v1 | 一致 | ✅ |
| p06 | trigger / pinyin-orthography | 一致 | ✅ 已修复 |
| p07–p09 | no_trigger | 一致（首轮输出存在 decision 字段与 reason 不一致的格式噪声，已单独复测三条诱饵，均为 no_trigger） | ✅ |
| p10 | trigger / pinyin-orthography | 一致 | ✅ 已修复 |
| p11 | trigger / level-scoping + 降级方案 | 一致 | ✅ 已修复 |
| p12 | trigger / classroom-diagnosis | 一致 | ✅ |

**触发与路由通过率 12/12 = 100%。**

## 未覆盖的验证维度（诚实标注）

本次盲测只验证**是否激活、路由到哪张卡**。以下两点属输出质量，机械化判分无法覆盖，只能由卡的正文约束：

- p10 要求"标注非本库来源"是否真的做到 → 由 `pinyin-orthography.md` 的 E 步 6 与 B 段兜底，未做行为验证。
- p11 的"单元级骨架"是否真的引用了量化指标 → 由 `level-scoping.md` 的 E 段兜底，未做行为验证。

**建议**：真实使用 20 次后，把出现偏差的回答补进 `test-prompts.json` 的 `edge_case`，再喂 darwin-skill 做 ratcheting。

## 复现方式

```bash
# 盲测：把 dist/hanyu-teacher-lesson-prep/ 交给一个干净 sub-agent，只给它下面 12 条 prompt
python -c "import json;d=json.load(open('.cangjie/capabilities/test-prompts.json',encoding='utf-8'));[print(c['prompt']) for c in d['test_cases']]"
```
