# 论文文本对齐审查

本目录用于审查论文文本与当前项目代码/文档现状的一致性，重点识别“蓝图目标”与“当前实现”之间的偏差。

## 文件

1. [thesis-text-alignment-review-v1.md](./thesis-text-alignment-review-v1.md)
   论文总审查报告，按架构、算法、数据面、测试与结论多个维度分析需要调整的地方。

2. [thesis-adjustment-matrix-v1.md](./thesis-adjustment-matrix-v1.md)
   逐章节调整矩阵，给出“论文原表述问题 -> 证据 -> 推荐改法”。

3. [thesis-software-engineering-supplement-v1.md](./thesis-software-engineering-supplement-v1.md)
   面向传统软件工程评审的补强方案，补充总体架构、模块划分、实体关系、流程时序、数据流转等内容。

4. [thesis-insertable-descriptions-v1.md](./thesis-insertable-descriptions-v1.md)
   可直接改写入论文的描述模板，覆盖系统总体架构、数据库逻辑结构、关键流程和数据流转。

5. [thesis-figure-prompts-v1.md](./thesis-figure-prompts-v1.md)
   论文图表专用提示词模板库，包含 AI 生图 Prompt 与可直接用于 Mermaid / draw.io 的图代码草稿。

6. [thesis-placeholder-figure-prompts-v2.md](./thesis-placeholder-figure-prompts-v2.md)
   按论文正文中的实际占位编号汇总的图表提示词索引，直接对应 `图4-1 / 图5-3 / 图6-1` 等，占位查找更方便。

7. [thesis-figure-structured-code-v1.md](./thesis-figure-structured-code-v1.md)
   面向 `draw.io / Mermaid` 的结构化代码包，重点覆盖 `图4-3 / 图4-4 / 图5-3 / 图5-4`。

8. [thesis-figure-gap-and-mechanism-expansion-v1.md](./thesis-figure-gap-and-mechanism-expansion-v1.md)
   从“图表缺口、第六章补强、非结构化机制图扩展”三个角度，分析论文当前还缺什么、优先补什么。

9. [thesis-priority-figure-table-pack-v1.md](./thesis-priority-figure-table-pack-v1.md)
   面向当前最优先补完的 8 项图表，统一提供生成方式、详细内容、Prompt、Mermaid 草稿与表格模板。

10. [thesis-chapter6-redesign-v1.md](./thesis-chapter6-redesign-v1.md)
   面向第 6 章《系统测试与结果分析》的重构方案，包含新版章节文本、图表建议、日志截图与专业化补强方法。

11. [thesis-log-sample-and-screenshot-plan-v1.md](./thesis-log-sample-and-screenshot-plan-v1.md)
   面向第 6 章日志样例与终端截图材料的专项方案，包含推荐测试场景、关键日志节选、示例 JSONL 与截图配置建议。

12. [thesis-mechanism-figure-prompts-v2.md](./thesis-mechanism-figure-prompts-v2.md)
   面向论文机制图的专业生图提示词包，重点覆盖图5-Y、图5-Z、图5-X、图1-Y、图6-X 等非结构化解释图。
