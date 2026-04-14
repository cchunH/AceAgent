# 论文占位图提示词汇总 v2

## 1. 文档用途

本文档专门服务于 [papertxt.txt](/mnt/d/ProjectSpace/Uni-Mind/PaperWorkSpace/papertxt.txt) 中已经出现的图表占位，按论文内的实际编号统一汇总，避免在多个图表模板文件中来回寻找。

适用对象：

1. `AI 生图模型`
- 如 Gemini、GPT-Image、通用科研绘图模型
- 直接复制 `强化版 Prompt` 使用

2. `draw.io / Visio / ProcessOn / 亿图`
- 可先用提示词生成草图
- 再按“结构要点”手工复刻

3. `Mermaid`
- 本文不重复堆叠 Mermaid 代码
- 若需要结构草稿，可继续参考 [thesis-figure-prompts-v1.md](/mnt/d/ProjectSpace/Uni-Mind/docs/paper-review/thesis-figure-prompts-v1.md)

约束说明：

- 图中所有可见文本必须是中文。
- 风格必须是本科软件工程论文可接受的学术技术图，而不是宣传海报。
- 如果某张图更适合手工绘制，文中会明确标注。

## 2. 论文占位图总览

| 论文占位 | 章节位置 | 图名 | 图类型 | 推荐方式 |
|---|---|---|---|---|
| 图4-1 | 第4.1节 | 系统总体架构图 | 分层架构图 | AI草图 + 手工精修 |
| 图4-2 | 第4.2节 | 功能模块划分图 | 模块树/分层模块图 | AI或手工均可 |
| 图4-3 | 第4.3节 | 智能体任务执行全生命周期时序图 | UML时序图 | Mermaid/手工优先 |
| 图4-4 | 第4.4节 | 系统逻辑数据模型与实体关系图 | E-R / 逻辑数据模型图 | 手工优先 |
| 表4-1 | 第4.4节 | 核心逻辑数据结构设计表 | 逻辑表设计 | 直接制表 |
| 图5-1 | 第5.1.1节 | 稀疏特征拓扑锚点识别流程图 | 算法流程图 | AI或手工均可 |
| 图5-2 | 第5.1.2节 | 动态场景去噪与静态骨架提取流程图 | 算法流程图 | AI或手工均可 |
| 图5-3 | 第5.3.2节 | 闭环校验与异常自愈流程图 | 闭环流程图 | AI或手工均可 |
| 图5-4 | 第5.4.1节 | 认知回灌与蓝图热修复流程图 | 反馈闭环图 | AI草图 + 手工精修 |
| 图6-1 | 第6.1节 | 测试框架与验证闭环图 | 测试体系图 | AI或手工均可 |

## 3. 全局总前缀

下面这段可以作为所有图片 Prompt 的固定前缀。

```text
[Style & Meta-Instructions]
High-fidelity academic schematic, software engineering thesis figure, clean white background, strict 2D vector style, crisp edges, no photorealism, no texture noise, no artistic abstraction. All visible labels, titles, captions, module names, arrows, annotations, and legends must be in Chinese only. Use a clean Chinese academic figure style suitable for undergraduate software engineering thesis defense and journal-style technical documentation.

[Typography Rules]
All on-figure text must be simplified Chinese. Use short Chinese labels, high readability, dark gray text, no English labels inside the figure. Keep labels aligned and evenly spaced.

[Color Rules]
Use low-saturation professional colors: blue-gray, teal, orange, green, and light purple as auxiliary. White background. Different modules should have distinct but restrained colors. Important paths use darker blue or orange arrows. Do not use neon colors.

[Layout Rules]
Strong modular boundaries, clear directional arrows, balanced spacing, no overcrowding, visually symmetric where appropriate. Use rounded rectangles for modules, database cylinders for storage, document icons for data objects, monitor/phone icons for device environment, gear icons for processing modules.

[Output Requirement]
Generate a thesis-ready technical figure. Do not draw decorative elements. Focus on software architecture clarity, data flow clarity, and Chinese academic annotation quality.
```

## 4. 图4-1 系统总体架构图

### 4.1 图义定位

- 用于说明全系统的分层结构、主执行链路、反馈链路与知识沉淀位置。
- 应以“分层职责”优先，而不是把所有执行细节都塞进去。

### 4.2 结构要点

1. 顶部为 `交互层`
2. 中上为 `战略推理层`
3. 中部为 `反应执行层`
4. 中下为 `知识沉淀层`
5. 底部为 `基础设施层`
6. 仅保留三类箭头：
- 主执行流
- 校验/重规划流
- 结果回灌/用户反馈流

### 4.3 强化版 Prompt

```text
---BEGIN PROMPT---
[Style & Meta-Instructions]
High-fidelity academic software architecture diagram, thesis-ready, clean white background, strict 2D vector style. All visible labels must be in Chinese only.

[Layout Configuration]
Selected Layout: strict hierarchical layered architecture with 5 horizontal layers
Composition Logic: a clean top-down layered stack, each layer wrapped in a large rounded rectangle container, only main control flow and feedback flow are shown, avoid excessive crossing arrows
Color Palette: blue-gray for interaction and infrastructure, teal for strategic planning, warm blue and mint green for execution, green and light purple for knowledge and update modules

[Layer 1: 交互层]
Full-width rounded rectangle at top
Internal nodes: "用户输入", "自然语言任务", "执行结果反馈"
Use user icon, document icon, message bubble icon

[Layer 2: 战略推理层]
Second horizontal band
Internal modules from left to right: "多模态意图解析", "任务拆解", "局部重规划", "意图契约生成"
These are planning modules, not storage objects

[Layer 3: 反应执行层]
Third horizontal band, the largest processing area
Internal modules arranged in two rows:
Row 1: "界面感知", "锚点拓扑匹配", "动态去噪与静态骨架"
Row 2: "仿射映射", "动作执行", "前置断言与后置校验"
Use gear icons only on processing-heavy modules

[Layer 4: 知识沉淀层]
Fourth horizontal band
Split into two sub-zones:
Left storage sub-zone: "任务蓝图库", "拓扑指纹索引", "向量检索层"
Right update sub-zone: "认知回灌与补丁更新"
Storage modules should be cylinders, update module should be rounded rectangle with patch/document icon

[Layer 5: 基础设施层]
Bottom horizontal band
Internal nodes: "Android运行环境", "ADB控制通道", "外部推理服务", "日志与本地存储"
This layer should be named 基础设施层, not 基础环境层

[Arrow Rules]
Dark blue solid arrows: main execution flow from top to bottom
Orange solid arrows: validation / replan / repair flow
Deep blue side feedback arrows: execution result feedback to user and update feedback to strategic layer
Do not let more than two arrows overlap on the right side

[Legend]
Include a small legend at the bottom-right:
"蓝色实线：主执行流"
"橙色实线：校验与修复流"
"深蓝回路：反馈流"
"圆柱：存储对象"
"圆角矩形：功能模块"

[Special Requirement]
This figure must look like a formal undergraduate software engineering thesis architecture figure. Emphasize clear layer boundaries, module responsibility consistency, and minimal but meaningful arrows. All text in Chinese only.
---END PROMPT---
```

## 5. 图4-2 功能模块划分图

### 5.1 图义定位

- 用于说明“系统由哪些模块构成”。
- 这张图应是模块树，不应混入复杂反馈箭头。

### 5.2 结构要点

1. 根节点：`层次化智能体决策架构`
2. 二级节点：
- `战略推理层`
- `反应执行层`
- `知识沉淀层`
- `基础设施层`
3. 三级节点写成模块，而不是流程阶段

### 5.3 强化版 Prompt

```text
---BEGIN PROMPT---
[Style & Meta-Instructions]
Academic software module decomposition diagram, clean vector style, white background, all labels in Chinese only.

[Layout Configuration]
Selected Layout: top-down module tree
Composition Logic: one root node at top center, four major branch nodes below, each branch expanded into clear submodules, no crossing lines, no feedback arrows

[Root Node]
"层次化智能体决策架构"

[Second Level Nodes]
"战略推理层"
"反应执行层"
"知识沉淀层"
"基础设施层"

[Third Level Nodes]
Under 战略推理层:
"多模态意图解析"
"任务拆解"
"局部重规划"
"意图契约生成"

Under 反应执行层:
"界面感知"
"锚点拓扑匹配"
"动态去噪与静态骨架"
"仿射映射"
"动作执行"
"前置断言与后置校验"

Under 知识沉淀层:
"任务蓝图库"
"拓扑指纹索引"
"向量检索层"
"认知回灌与补丁更新"

Under 基础设施层:
"Android运行环境"
"ADB控制通道"
"外部推理服务"
"日志与本地存储"

[Visual Rules]
Each branch must use one restrained color family
All node labels must be short and centered
Root node larger than all others
Rounded rectangles only, no database cylinders in this figure

[Special Requirement]
This must read as a functional decomposition chart, not as a workflow chart. Chinese only.
---END PROMPT---
```

## 6. 图4-3 智能体任务执行全生命周期时序图

### 6.1 图义定位

- 用于说明一次任务从输入到反馈的动态过程。
- 这张图更适合 `Mermaid 或手工绘制`，AI 生图容易把 lifeline 画乱。

### 6.2 参与者

1. 用户
2. 战略推理层
3. 知识沉淀层
4. 反应执行层
5. 移动设备

### 6.3 强化版 Prompt

```text
---BEGIN PROMPT---
[Style & Meta-Instructions]
Formal UML-style sequence diagram for undergraduate software engineering thesis, white background, strict vector line style, all labels in Chinese only.

[Layout Configuration]
Selected Layout: strict left-to-right sequence diagram with vertical lifelines
Composition Logic: five lifelines with clear message order from top to bottom, activation bars visible, return messages dashed, no decorative icons

[Participants]
"用户"
"战略推理层"
"知识沉淀层"
"反应执行层"
"移动设备"

[Message Flow]
1. 用户 -> 战略推理层: "输入自然语言任务"
2. 战略推理层 -> 战略推理层: "解析意图并拆解任务"
3. 战略推理层 -> 知识沉淀层: "查询蓝图与拓扑候选"
4. 知识沉淀层 --> 战略推理层: "返回候选结果"
5. 战略推理层 -> 反应执行层: "下发意图契约"
6. 反应执行层 -> 移动设备: "获取当前界面"
7. 移动设备 --> 反应执行层: "返回感知结果"
8. 反应执行层 -> 反应执行层: "拓扑匹配与前置断言"
9. 反应执行层 -> 移动设备: "执行动作"
10. 移动设备 --> 反应执行层: "返回执行后状态"
11. 反应执行层 -> 反应执行层: "后置校验"
12. 反应执行层 -> 知识沉淀层: "回灌轨迹并更新蓝图"
13. 反应执行层 --> 用户: "返回执行结果"

[Visual Rules]
Solid arrows for request messages
Dashed arrows for return messages
Gray thin lifelines
Blue request arrows, orange feedback arrows

[Special Requirement]
This must look like a clean textbook UML sequence diagram. Chinese labels only. The timing order must be absolutely clear.
---END PROMPT---
```

## 7. 图4-4 系统逻辑数据模型与实体关系图

### 7.1 图义定位

- 这是论文中最传统的软件工程图之一。
- 目标不是还原真实物理数据库，而是让评审理解你的逻辑数据结构。

### 7.2 实体建议

1. 用户意图
2. 任务蓝图
3. 拓扑指纹
4. 原子动作
5. 运行任务
6. 运行事件
7. 蓝图补丁

### 7.3 强化版 Prompt

```text
---BEGIN PROMPT---
[Style & Meta-Instructions]
Professional logical ER diagram for software engineering thesis, clean white background, strict 2D vector style, all visible labels must be in Chinese only.

[Layout Configuration]
Selected Layout: center-out relational schema
Composition Logic: "任务蓝图" as the central entity, six related entities distributed around it, straight relationship lines, no excessive decoration

[Entity Boxes]
Center: "任务蓝图"
Left: "用户意图", "原子动作"
Right: "拓扑指纹", "蓝图补丁"
Bottom: "运行任务", "运行事件"

[Fields]
Inside each entity box show 3 to 5 Chinese fields
"用户意图": "意图主键", "原始指令", "标准意图键"
"任务蓝图": "蓝图主键", "意图键", "版本号", "目标状态"
"拓扑指纹": "指纹主键", "骨架签名", "稳定度"
"原子动作": "动作主键", "动作类型", "动作参数", "顺序号"
"运行任务": "运行主键", "任务状态", "提交时间"
"运行事件": "事件主键", "事件类型", "时间戳"
"蓝图补丁": "补丁主键", "目标蓝图", "补丁版本"

[Relationships]
"用户意图" 1-to-many "任务蓝图"
"任务蓝图" 1-to-many "原子动作"
"任务蓝图" 1-to-1 or 1-to-many "拓扑指纹"
"任务蓝图" 1-to-many "蓝图补丁"
"运行任务" 1-to-many "运行事件"
"运行任务" many-to-1 "用户意图"
"运行事件" many-to-1 "任务蓝图"

[Visual Rules]
Entity rectangles in light gray-blue
Core entity "任务蓝图" slightly darker
Relationship labels in concise Chinese such as "对应", "包含", "依赖", "产生", "更新"

[Special Requirement]
The figure must look like a thesis logical data model diagram understandable by traditional software engineering reviewers. All text in Chinese only.
---END PROMPT---
```

## 8. 表4-1 核心逻辑数据结构设计表

### 8.1 这不是图片

- 这项占位建议直接做成论文表格，不建议生图。
- 表头建议统一如下：

| 实体名称 | 核心字段 | 数据类型 | 主外键关系 | 作用说明 |
|---|---|---|---|---|

### 8.2 建议纳入的实体

1. 用户意图
2. 任务蓝图
3. 拓扑指纹
4. 原子动作
5. 运行任务
6. 运行事件
7. 蓝图补丁

## 9. 图5-1 稀疏特征拓扑锚点识别流程图

### 9.1 图义定位

- 重点是算法流程，不是架构分层。
- 建议有一个判断框：锚点稳定性是否达标。

### 9.2 强化版 Prompt

```text
---BEGIN PROMPT---
[Style & Meta-Instructions]
Algorithm flowchart for software engineering thesis, clean vector style, white background, all labels in Chinese only.

[Layout Configuration]
Selected Layout: top-down flowchart with one decision loop
Composition Logic: vertical flow from start to end, one decision diamond in middle, one loop-back arrow on the left side

[Flow Nodes]
"开始"
"输入界面感知结果"
"提取文字节点与图标节点"
"坐标归一化"
"特征编码"
"划分主锚点与辅锚点"
"锚点稳定性评估"
"计算距离比例与角度特征"
"生成拓扑指纹"
"输出锚点集合与匹配依据"
"结束"

[Decision Node]
"锚点稳定性是否满足要求"

[Logic]
Start -> input -> extract nodes -> normalize -> encode -> split anchors -> stability evaluation -> decision
If yes -> compute topology features -> generate topology fingerprint -> output -> end
If no -> return to extract nodes

[Visual Rules]
Gray rounded rectangles for process blocks
Orange diamond for decision node
Blue arrows for normal path
Orange loop arrow for retry path

[Special Requirement]
This figure must read as a textbook algorithm flowchart with strict Chinese labels only.
---END PROMPT---
```

## 10. 图5-2 动态场景去噪与静态骨架提取流程图

### 10.1 图义定位

- 重点展示“多帧采样 -> 稳定性评分 -> 动态区屏蔽 -> 静态骨架输出”。

### 10.2 强化版 Prompt

```text
---BEGIN PROMPT---
[Style & Meta-Instructions]
Academic algorithm flowchart, clean software thesis style, white background, all labels in Chinese only.

[Layout Configuration]
Selected Layout: top-down processing flow with one side branch for dynamic noise masking
Composition Logic: main vertical pipeline, side branch showing noisy regions being masked out, final output at bottom

[Main Flow Nodes]
"开始"
"输入多帧界面样本"
"跨帧节点对齐"
"计算出现频率与位置漂移"
"稳定性评分"
"提取静态候选节点"
"重建静态骨架"
"输出骨架与稳定锚点"
"结束"

[Side Branch Nodes]
"识别高波动区域"
"标记动态噪音区"
"应用掩模矩阵"

[Logic]
Main path from top to bottom
After "稳定性评分", split:
Branch A -> "提取静态候选节点"
Branch B -> "识别高波动区域" -> "标记动态噪音区" -> "应用掩模矩阵"
Then both paths merge into "重建静态骨架"

[Visual Rules]
Blue-gray for main path
Orange for dynamic noise branch
Green for final stable output

[Special Requirement]
The figure must emphasize temporal sampling and static-versus-dynamic separation. Chinese labels only.
---END PROMPT---
```

## 11. 图5-3 闭环校验与异常自愈流程图

### 11.1 图义定位

- 这是论文里很关键的“闭环图”。
- 应突出：
  - 执行前断言
  - 执行后校验
  - 微扰重试
  - 重规划

### 11.2 强化版 Prompt

```text
---BEGIN PROMPT---
[Style & Meta-Instructions]
Formal closed-loop validation and self-recovery flowchart, undergraduate thesis style, white background, vector only, all labels in Chinese only.

[Layout Configuration]
Selected Layout: cyclic flowchart with two decision diamonds
Composition Logic: a central vertical main execution path, exception handling branch on the right, loop-back arrow to the top

[Main Flow]
"接收动作请求"
"执行前局部感知"
"前置语义断言"
"执行物理动作"
"采集执行后状态"
"后置校验"
"任务成功"

[Decision Nodes]
"目标区域是否匹配意图"
"界面状态是否符合预期"

[Recovery Nodes]
"阻断执行"
"微扰重试"
"局部重规划"
"蓝图热修复"

[Logic]
接收动作请求 -> 执行前局部感知 -> 决策1
If 决策1 yes -> 前置语义断言 -> 执行物理动作 -> 采集执行后状态 -> 决策2
If 决策2 yes -> 任务成功
If 决策2 no -> 微扰重试 -> 局部重规划 -> 蓝图热修复 -> return to 接收动作请求
If 决策1 no -> 阻断执行 -> 局部重规划 -> return to 接收动作请求

[Visual Rules]
Blue for normal execution path
Orange for exception branch
Green for successful completion
Decision diamonds visually prominent

[Special Requirement]
The recovery loop must be visually stronger than ordinary arrows. Chinese labels only.
---END PROMPT---
```

## 12. 图5-4 认知回灌与蓝图热修复流程图

### 12.1 图义定位

- 用于表现“成功轨迹如何回灌成蓝图更新”。
- 这张图建议画成环形闭环，而不是普通流程图。

### 12.2 强化版 Prompt

```text
---BEGIN PROMPT---
[Style & Meta-Instructions]
Academic feedback-loop schematic for software engineering thesis, clean white background, strict 2D vector style, all labels in Chinese only.

[Layout Configuration]
Selected Layout: clockwise cyclic loop with 5 major nodes
Composition Logic: a circular loop showing successful runtime sample being analyzed, patched, updated, and reused

[Nodes]
Top: "成功执行轨迹"
Upper-right: "差分分析"
Right-bottom: "稳定锚点与骨架提炼"
Bottom: "蓝图补丁生成与热修复"
Left: "蓝图库更新与下次命中"

[Center Annotation]
"从高成本推理到低成本复用"

[Arrow Rules]
Clockwise thick arrows between all nodes
One highlighted feedback arrow from "蓝图库更新与下次命中" back to "成功执行轨迹"

[Visual Rules]
Green for successful runtime sample
Orange for analysis and patch generation
Blue-gray for repository update and reuse
Use blueprint document icon, patch icon, repository cylinder icon

[Special Requirement]
This figure must emphasize iterative optimization, reuse, and controlled blueprint evolution. Chinese only.
---END PROMPT---
```

## 13. 图6-1 测试框架与验证闭环图

### 13.1 图义定位

- 用于说明“测试环境、测试任务、评估维度、输出指标”的关系。
- 目标是让第 6 章看起来更像规范的软件工程验证。

### 13.2 强化版 Prompt

```text
---BEGIN PROMPT---
[Style & Meta-Instructions]
Academic software testing framework diagram, thesis-ready vector style, white background, all visible labels in Chinese only.

[Layout Configuration]
Selected Layout: left-to-right layered evaluation framework
Composition Logic: environment block on the left, test task block in the middle, evaluation dimension block on the right, output metrics block at the bottom-right or far right

[Zone 1: 测试环境]
"Android设备"
"ADB驱动"
"模型服务"
"日志系统"

[Zone 2: 测试任务集]
"原子交互任务"
"跨应用任务"
"异常场景任务"

[Zone 3: 评估维度]
"功能完整性"
"响应效率"
"跨设备适配"
"异常处理能力"

[Zone 4: 输出指标]
"任务成功率"
"平均响应时间"
"推理开销"
"回退触发率"

[Connections]
测试环境 -> 测试任务集 -> 评估维度 -> 输出指标
Add one feedback arrow from 输出指标 back to 测试任务集 labeled "结果复核"

[Visual Rules]
Blue-gray environment zone
Teal task zone
Orange evaluation zone
Green or blue output metric zone
Use clean containers and consistent spacing

[Special Requirement]
This figure must look like a serious thesis testing framework overview, not a business dashboard. Chinese only.
---END PROMPT---
```

## 14. 使用建议

### 14.1 最适合直接生图的

1. 图4-1 系统总体架构图
2. 图4-2 功能模块划分图
3. 图5-1 稀疏特征拓扑锚点识别流程图
4. 图5-2 动态场景去噪与静态骨架提取流程图
5. 图5-3 闭环校验与异常自愈流程图
6. 图5-4 认知回灌与蓝图热修复流程图
7. 图6-1 测试框架与验证闭环图

### 14.2 更适合 Mermaid / 手工绘制的

1. 图4-3 智能体任务执行全生命周期时序图
2. 图4-4 系统逻辑数据模型与实体关系图
3. 表4-1 核心逻辑数据结构设计表

### 14.3 推荐出图顺序

1. 图4-1
2. 图4-2
3. 图4-3
4. 图4-4
5. 图5-3
6. 图5-4
7. 图6-1

这样可以优先补齐评审最敏感的“总体架构、模块划分、时序、数据模型、闭环、测试”。
