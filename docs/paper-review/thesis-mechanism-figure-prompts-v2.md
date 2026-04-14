# 论文机制图专业生图提示词包 v2

## 1. 文档目的

本文档专门面向论文中的“机制图 / 原理图 / 非结构化解释图”，提供一组更适合计算机领域论文的专业生图提示词。

与流程图、E-R 图、时序图不同，这类图片的任务是：

1. 把抽象的系统机制讲直观
2. 补强论文中最难理解但最有创新性的部分
3. 提升答辩展示效果

本包优先覆盖当前最值得补的机制图：

1. `图5-Y 自然语言指令到标准化意图契约的收敛示意图`
2. `图5-Z 从即时推理到蓝图复用的成本迁移示意图`
3. `图5-X 主锚点与辅锚点的星座式拓扑示意图`
4. `图1-Y 移动智能体技术演进路径示意图`
5. `图6-X 测试任务覆盖面示意图`

## 2. 通用使用规则

所有机制图都建议遵守以下约束：

### 2.1 文本规则

1. 图中所有可见文字必须是中文。
2. 标签尽量简短，单个标签优先控制在 10 个字以内。
3. 术语保持与论文正文一致，例如：
   - `战略推理层`
   - `反应执行层`
   - `知识沉淀层`
   - `意图契约`
   - `蓝图复用`

### 2.2 风格规则

1. 白底
2. 严格 2D 矢量风格
3. 不要照片感、不要写实材质、不要发光特效
4. 视觉风格应接近“本科软件工程论文插图”或“学术技术图”
5. 线条干净、边界清晰、模块明确

### 2.3 颜色规则

1. 主色推荐：
   - 蓝灰
   - 青绿
   - 橙色
   - 低饱和绿色
2. 红色仅用于表示高成本、高风险或高不确定性
3. 避免彩虹色、霓虹色、夸张渐变

### 2.4 图标规则

计算机论文中允许使用简化图标，但必须服务于结构表达。推荐图标包括：

1. 文档/对话框：表示自然语言输入或日志
2. 手机轮廓：表示移动端界面
3. 芯片/模块块：表示算法网关或推理模块
4. 圆柱数据库：表示知识库、别名库、蓝图库
5. 小圆点/连线：表示锚点与拓扑
6. 箭头：表示数据流、收敛流、反馈流、成本迁移

## 3. 图5-Y 自然语言指令到标准化意图契约的收敛示意图

### 3.1 用途定位

本图用于解释：

1. 为什么自然语言输入不会直接变成随机动作
2. 为什么系统需要意图对齐网关
3. 为什么多样表达最终能收敛到统一契约

这是第 5 章最值得补的一张机制图。

### 3.2 推荐布局

- 主布局：`Linear Pipeline + Central Hub`
- 画面逻辑：左侧多输入，中间收敛网关，右侧统一契约，底部支撑库

### 3.3 最终生图提示词

```text
---BEGIN PROMPT---
[Style & Meta-Instructions]
High-fidelity scientific schematic for a computer science thesis, software architecture mechanism figure, clean white background, strict 2D vector illustration, crisp edges, no photorealistic texture, no decorative background. All visible labels, titles, annotations, legends, and arrows must be in Chinese only. The figure must look like a formal undergraduate software engineering thesis diagram.

[LAYOUT CONFIGURATION]
Selected Layout: Left-to-right convergence mechanism with bottom support modules
Composition Logic: multiple natural language inputs on the left converge into a central intent alignment gateway, then map into one standardized intent contract on the right. At the bottom, three support repositories feed the gateway and the final contract.
Color Palette: Blue-gray for input expressions, teal for the alignment gateway, orange for the standardized contract, muted green for support repositories.

[ZONE 1: LEFT - 多样自然语言输入]
Container: left vertical cluster of rounded speech/document boxes
Visual Structure: four separate dialogue bubbles or paper cards aligned vertically, each containing a different user expression
Key Text Labels:
"帮我把蓝牙打开"
"去设置里开启蓝牙"
"把这个开关打开"
"打开手机蓝牙"

[ZONE 2: CENTER - 意图对齐网关]
Container: large central rounded rectangle with inner submodules
Visual Structure: one gateway block containing three inner stacked modules, each with a small chip or gear icon
Key Text Labels:
"意图对齐网关"
"语义向量化"
"相似度匹配"
"别名归一"

[ZONE 3: RIGHT - 标准化意图契约]
Container: right-side contract card or document panel with a strong boundary
Visual Structure: one structured contract object with four visible fields arranged top to bottom
Key Text Labels:
"标准化意图契约"
"应用域：系统设置"
"动作原语：切换开关"
"操作对象：蓝牙"
"断言规则：状态已开启"

[ZONE 4: BOTTOM-LEFT - 支撑知识]
Container: bottom row of three small repository blocks with database cylinder icons
Visual Structure: three separate support modules
Key Text Labels:
"意图别名库"
"动作原语集合"
"语义断言规则"

[CONNECTIONS]
1. Multiple medium blue arrows from each natural language input in Zone 1 toward the central gateway in Zone 2.
2. One thick teal arrow from Zone 2 to the standardized contract in Zone 3 labeled "收敛".
3. Thin support arrows from "意图别名库" and "动作原语集合" to the gateway.
4. Thin support arrow from "语义断言规则" to the standardized contract.

[VISUAL EMPHASIS]
The central gateway must visually appear as the key reasoning node.
The right-side contract must look structured and deterministic.
The overall image must clearly convey many-to-one semantic convergence.
---END PROMPT---
```

## 4. 图5-Z 从即时推理到蓝图复用的成本迁移示意图

### 4.1 用途定位

本图用于解释：

1. 冷路径为什么慢、贵、不稳定
2. 认知回灌中间做了什么
3. 热路径为什么更快、更省、更稳定

这是解释“蓝图复用价值”的最佳机制图。

### 4.2 推荐布局

- 主布局：`Linear Pipeline`
- 画面逻辑：左高成本，中间编译/回灌，右低成本复用，附带一个小型持续优化回环

### 4.3 最终生图提示词

```text
---BEGIN PROMPT---
[Style & Meta-Instructions]
High-fidelity scientific schematic for a computer systems thesis, clean white background, formal 2D vector illustration, academic software engineering style. No photorealism, no hand-drawn effect, no decorative clutter. All visible text must be Chinese only.

[LAYOUT CONFIGURATION]
Selected Layout: Left-to-right cost migration pipeline with one feedback loop
Composition Logic: the left side shows expensive cold-start inference, the center shows cognitive compilation and patch generation, the right side shows efficient blueprint reuse. A thin loop from the right returns to the center to indicate continuous optimization.
Color Palette: warm orange-red for high-cost zone, teal-blue for compilation zone, green-blue for low-cost reuse zone.

[ZONE 1: LEFT - 冷启动即时推理]
Container: large warm-colored panel
Visual Structure: stacked modules with high-cost visual cues, such as a large model chip, multiple document stacks, and a long path arrow
Key Text Labels:
"冷启动即时推理"
"全量界面感知"
"多模态推理"
"高Token开销"
"高响应时延"

[ZONE 2: CENTER - 认知回灌与编译]
Container: central medium-sized processing block with three internal nodes
Visual Structure: a compilation engine with gear, diff document, and blueprint patch icons
Key Text Labels:
"认知回灌"
"差分分析"
"稳定锚点提炼"
"蓝图补丁生成"
"蓝图库更新"

[ZONE 3: RIGHT - 热路径蓝图复用]
Container: large cool-colored panel
Visual Structure: one compact execution path with a blueprint card, topology match icon, and a short fast arrow
Key Text Labels:
"热路径蓝图复用"
"拓扑快速命中"
"低成本导航执行"
"较低Token开销"
"较短响应时间"

[CONNECTIONS]
1. One thick arrow from Zone 1 to Zone 2 labeled "经验沉淀".
2. One thick arrow from Zone 2 to Zone 3 labeled "蓝图实例化".
3. One curved dotted arrow looping back from Zone 3 to Zone 2 labeled "持续优化".

[VISUAL EMPHASIS]
The left zone must appear visually heavier and slower.
The right zone must appear visually lighter and shorter.
The center zone must look like a compilation bridge between expensive reasoning and efficient reuse.
---END PROMPT---
```

## 5. 图5-X 主锚点与辅锚点的星座式拓扑示意图

### 5.1 用途定位

本图用于解释：

1. 主锚点为什么是定位主基准
2. 辅锚点为什么能帮助局部修正
3. 动态区域为何被弱化而不参与稳定骨架

这张图不是流程图，而是“空间拓扑直觉图”。

### 5.2 推荐布局

- 主布局：`Central Hub`
- 画面逻辑：中间一块手机界面轮廓，内部用锚点和连线形成“星座”，边上标出主锚点、辅锚点、动态区

### 5.3 最终生图提示词

```text
---BEGIN PROMPT---
[Style & Meta-Instructions]
Technical mechanism diagram for a computer vision and GUI automation thesis, clean white background, strict 2D vector style, neat mobile UI outline, no photorealism. All visible text must be Chinese only.

[LAYOUT CONFIGURATION]
Selected Layout: Central hub topology schematic
Composition Logic: a smartphone interface outline in the center contains a constellation-like anchor graph. Core anchors, auxiliary anchors, and dynamic noisy regions are visually distinguished.
Color Palette: dark blue for core anchors, light teal for auxiliary anchors, light gray for static UI, pale orange transparent overlay for dynamic noisy region.

[ZONE 1: CENTER - 手机界面与拓扑骨架]
Container: central smartphone frame
Visual Structure: simplified mobile screen with several text blocks and icon blocks, overlaid by a graph of connected anchor points
Key Text Labels:
"主锚点"
"辅锚点"
"静态骨架"

[ZONE 2: WITHIN SCREEN - 锚点星座]
Container: overlay graph inside the phone screen
Visual Structure: 3 to 4 large dark nodes as core anchors, 5 to 7 smaller nodes as auxiliary anchors, solid lines connecting them into a stable topology
Key Text Labels:
"地址文本块"
"搜索框"
"确认按钮"
"图标组"

[ZONE 3: RIGHT SIDE - 说明面板]
Container: vertical legend panel
Visual Structure: legend with three marker types
Key Text Labels:
"主锚点：主定位基准"
"辅锚点：局部修正依据"
"动态区：弱化处理"

[ZONE 4: SCREEN CORNER - 动态区域]
Container: one or two semi-transparent highlighted patches inside the phone screen
Visual Structure: pale orange translucent region covering banner or animation area
Key Text Labels:
"动态噪音区"

[CONNECTIONS]
1. Fine lines connecting core anchors and auxiliary anchors inside the phone screen.
2. Small callout arrows from the legend to the corresponding elements.
3. Optional thin arrow from dynamic noisy region toward the legend labeled "弱化".

[VISUAL EMPHASIS]
Core anchors must be visibly larger and darker than auxiliary anchors.
The topology must feel stable and geometric.
Dynamic regions must appear visually de-emphasized and excluded from the core graph.
---END PROMPT---
```

## 6. 图1-Y 移动智能体技术演进路径示意图

### 6.1 用途定位

本图用于放在绪论中，解释你的研究为什么成立，路径是什么。

它不讲实现细节，而是讲技术阶段的演进关系。

### 6.2 推荐布局

- 主布局：`Linear Timeline`
- 画面逻辑：从左到右四阶段递进，阶段下方标优点和局限

### 6.3 最终生图提示词

```text
---BEGIN PROMPT---
[Style & Meta-Instructions]
Academic technology evolution figure for a computer science thesis, clean white background, strict 2D vector timeline style, textbook-like clarity. All visible labels must be in Chinese only.

[LAYOUT CONFIGURATION]
Selected Layout: Left-to-right timeline with four stages
Composition Logic: four chronological technical stages arranged horizontally, each stage shown as one large block with a small icon, strengths below, limitations below or beside it.
Color Palette: neutral gray-blue for early stages, teal for middle stage, orange-blue mixed for the final stage.

[ZONE 1: STAGE 1]
Container: left timeline block
Visual Structure: script icon and rigid process arrow
Key Text Labels:
"脚本自动化"
"优点：确定性强"
"局限：泛化能力弱"

[ZONE 2: STAGE 2]
Container: second timeline block
Visual Structure: one single-agent icon and one model chip
Key Text Labels:
"单智能体推理"
"优点：具备通用理解"
"局限：时延高、随机性强"

[ZONE 3: STAGE 3]
Container: third timeline block
Visual Structure: multiple small agent nodes connected to one task board
Key Text Labels:
"多智能体协作"
"优点：任务分工更细"
"局限：协同开销增大"

[ZONE 4: STAGE 4]
Container: rightmost emphasized block
Visual Structure: layered architecture icon with blueprint card and feedback loop
Key Text Labels:
"分层决策与知识沉淀"
"优点：兼顾效率与稳定性"
"局限：需要系统化工程支撑"

[CONNECTIONS]
1. Thick horizontal timeline arrow from Stage 1 to Stage 4.
2. Small transition arrows between adjacent stages.

[VISUAL EMPHASIS]
The final stage must be visually highlighted as the thesis target architecture.
The figure must feel chronological, rational, and engineering-oriented.
---END PROMPT---
```

## 7. 图6-X 测试任务覆盖面示意图

### 7.1 用途定位

本图用于说明第 6 章测试不是随意挑案例，而是覆盖了不同复杂度和不同扰动强度的任务。

### 7.2 推荐布局

- 主布局：`Matrix Layout`
- 画面逻辑：横轴任务复杂度，纵轴环境扰动强度，在格子中放任务类型

### 7.3 最终生图提示词

```text
---BEGIN PROMPT---
[Style & Meta-Instructions]
Academic test coverage mechanism figure for a software engineering thesis, clean white background, strict 2D vector style, grid-based layout, all visible labels in Chinese only.

[LAYOUT CONFIGURATION]
Selected Layout: Two-dimensional coverage matrix
Composition Logic: horizontal axis shows task complexity, vertical axis shows environment disturbance intensity. Several test task cards are placed inside the matrix cells.
Color Palette: blue-gray grid, teal task cards, orange highlight for complex and high-disturbance cells.

[ZONE 1: MATRIX FRAME]
Container: large central grid
Visual Structure: 3 by 3 matrix with labeled axes
Key Text Labels:
"任务复杂度"
"环境扰动强度"
"低"
"中"
"高"

[ZONE 2: TASK CARDS]
Container: multiple rounded cards placed in matrix cells
Visual Structure: one small card per task type
Key Text Labels:
"开关切换任务"
"跨应用导航任务"
"订单信息转发任务"
"弹窗干扰任务"
"布局微调任务"

[ZONE 3: LEGEND]
Container: small legend box in one corner
Visual Structure: color meaning explanation
Key Text Labels:
"基础任务"
"协同任务"
"异常场景任务"

[CONNECTIONS]
1. No heavy process arrows.
2. Keep emphasis on distribution of task cards across the matrix.

[VISUAL EMPHASIS]
The figure must clearly show that testing covers multiple difficulty levels and disturbance conditions.
The matrix must look systematic and evidence-oriented.
---END PROMPT---
```

## 8. 选图建议

如果你现在只准备补最值的机制图，优先顺序如下：

1. `图5-Y`
2. `图5-Z`
3. `图5-X`

如果还想补一张绪论或测试章的展示型机制图，再考虑：

4. `图1-Y`
5. `图6-X`

## 9. 使用建议

### 9.1 生图后仍建议手工精修

AI 生图适合用于：

1. 快速生成布局草图
2. 统一色调和模块关系
3. 获取较完整的初版视觉方案

但论文终稿建议仍做一次手工精修，尤其是：

1. 中文标签对齐
2. 箭头粗细一致
3. 模块边界统一
4. 图题与图注对应

### 9.2 不要让机制图和流程图重复

例如：

1. `图5-X` 是原理图，不要再画成流程图
2. `图5-Y` 是收敛图，不要和时序图重复
3. `图5-Z` 是成本迁移图，不要重新画成普通柱状图

机制图的职责是解释“为什么这样设计”，不是重复“系统怎么跑”。

## 10. 分步骤生图策略

针对 `图5-X 主锚点与辅锚点的星座式拓扑示意图`，不建议一次性直接生成“手机界面 + 拓扑锚点 + 图例 + 动态区”。  
更稳的方式是拆成两步：

1. 以聊天界面模板为参考，先生成标准化手机 UI 抽象底图并标出分区
2. 再基于该底图生成完整机制图，使锚点与关键区域贴合

这样做的核心价值是：

1. 可以先把屏幕中的关键区域位置固定下来
2. 再把主锚点、辅锚点放到正确的结构位置
3. 避免一次性生图时锚点漂浮、标签错位、动态区压住骨架的问题

### 10.1 推荐工作流

#### Step A：先生成聊天界面风格的手机 UI 抽象底图

目标：

1. 以类似微信聊天页面的纵向对话界面为模板
2. 抽象成适合论文的标准化手机 UI 底图
3. 明确标出后续可挂载锚点的关键分区
4. 不画拓扑线

必须包含：

1. 手机外框
2. 顶部状态栏与聊天标题栏
3. 中部消息流区域
4. 左右分布的消息气泡
5. 一到两个时间分隔标记
6. 底部输入栏与功能按钮区
7. 所有分区布局清晰、适合后续锚点覆盖

建议提示词：

```text
---BEGIN PROMPT---
[Style & Meta-Instructions]
Technical GUI base schematic for a computer science thesis, based on a mobile chat interface template, clean white background, strict 2D vector style, centered smartphone outline, no photorealism, no topology graph yet, no decorative clutter. All visible text must be Chinese only.

[LAYOUT CONFIGURATION]
Selected Layout: Central smartphone interface skeleton based on a chat UI
Composition Logic: one centered smartphone frame contains a simplified chat interface similar to a mobile instant messaging page. The UI must be abstracted into clear functional zones for later topology overlay.
Color Palette: light gray for neutral interface background, pale green for self message bubbles, white for peer message bubbles, medium gray for dividers and time labels, dark gray for phone outline.

[ZONE 1: TOP - 顶部导航区]
Container: top horizontal bar inside the phone
Visual Structure: status bar at the very top and a chat title/navigation bar below it
Key Text Labels:
"状态栏"
"聊天标题栏"

[ZONE 2: MIDDLE - 消息流主区]
Container: large central conversation area
Visual Structure: multiple alternating left and right message bubbles, two small time-divider labels between message groups
Key Text Labels:
"消息流区域"
"消息气泡组"
"时间分隔区"

[ZONE 3: LOWER - 输入操作区]
Container: bottom interaction bar
Visual Structure: one input box in the center, with voice, emoji, and plus-action icons arranged around it
Key Text Labels:
"输入栏"
"功能按钮区"

[ZONE 4: GLOBAL - 分区标注]
Container: subtle callout labels around the phone screen
Visual Structure: thin arrows or annotation tags pointing to the top navigation zone, message flow zone, and input operation zone
Key Text Labels:
"顶部导航区"
"消息流主区"
"底部输入区"

[VISUAL EMPHASIS]
The interface must feel like a standard abstracted chat page rather than a screenshot copy.
Keep the geometry regular and suitable for later anchor placement.
Do not generate any anchor points or topology edges in this stage.
---END PROMPT---
```

### 10.1.1 Step A 质量评估与修正方向

如果生成结果类似“带大量具体聊天文本、头像、功能按钮说明的完整聊天页”，说明它已经接近可用，但还不算最优的论文底图。  
更理想的底图应满足以下标准：

1. `分区明确`
- 顶部导航区、消息流主区、底部输入区必须一眼可分。

2. `内容抽象`
- 以结构块、气泡轮廓、时间标签、输入栏轮廓为主。
- 不应保留过多具体对话内容。

3. `标签适度`
- 只保留少量分区级标签。
- 不要把每个功能图标、每个头像都逐一解释。

4. `为锚点留空间`
- 消息气泡边缘、时间标签、标题栏边界、输入栏边界要清晰。
- 不能因为文本过多导致后续锚点无处可挂。

5. `避免误导性命名`
- 不建议在聊天页底部把手机系统三键区域标成“系统导航栏”，这会和应用内输入区混淆。
- 底图重点是应用 UI 结构，不是手机 OS 控件说明。

### 10.1.2 对当前样例图的判断

当前这张图 `基本合格，但仍偏“示意截图”，不够“抽象底图”`。

优点：

1. 顶部导航区、消息流主区、底部输入区三大分区已经成立。
2. 聊天气泡左右分布清楚，具备后续挂锚点的基础。
3. 时间分隔区被保留下来，这一点很好。

主要问题：

1. `具体文本过多`
- “好的”“大概什么时间呀”等具体对话内容太强，会让图更像聊天截图改绘，而不是通用结构底图。

2. `头像和功能点标注过细`
- “对端用户头像”“本端用户头像”“语音输入”“表情包”“更多功能”等标签太多，信息密度偏高。

3. `局部命名不够准确`
- 底部三键区域不建议作为底图重点结构。
- 聊天页底图应该突出“输入栏和功能按钮区”，弱化系统级控件。

4. `结构抽象程度还不够统一`
- 有些区域是抽象块，有些区域还是具体内容，视觉语言不统一。

### 10.1.3 更适合的 Step A 修正版提示词

如果你希望生成更像“论文底图”的版本，建议改用下面这个更收敛的提示词。

```text
---BEGIN PROMPT---
[Style & Meta-Instructions]
Technical GUI base schematic for a computer science thesis, based on a mobile chat interface, clean white background, strict 2D vector style, centered smartphone outline, no photorealism, no topology graph, no screenshot realism. All visible text must be Chinese only.

[LAYOUT CONFIGURATION]
Selected Layout: Central smartphone chat UI skeleton
Composition Logic: one centered smartphone frame contains an abstract instant messaging interface. The figure must emphasize structural zones rather than specific message content.
Color Palette: light gray for interface background, pale green for self-message bubbles, white for peer-message bubbles, medium gray for separators and time tags, dark gray for phone outline.

[ZONE 1: TOP - 顶部导航区]
Container: top horizontal region
Visual Structure: a clean title/navigation bar with simple left and right controls, no excessive detail
Key Text Labels:
"顶部导航区"
"标题栏"

[ZONE 2: CENTER - 消息流主区]
Container: large central conversation region
Visual Structure: alternating left-right message bubble blocks, two simple time-divider labels, minimal placeholder text only
Key Text Labels:
"消息流主区"
"消息气泡组"
"时间分隔区"

[ZONE 3: BOTTOM - 底部输入区]
Container: bottom input region
Visual Structure: one centered input box and a few simplified action icons around it
Key Text Labels:
"底部输入区"
"输入栏"
"功能按钮区"

[ABSTRACTION RULES]
1. Use short placeholder message text instead of detailed chat sentences.
2. Keep avatars as simple circles or omit detailed avatar semantics.
3. Do not label every icon individually.
4. Do not emphasize the phone system navigation buttons.
5. Maintain large blank margins around bubble edges for later anchor placement.

[VISUAL EMPHASIS]
The figure must look like an abstracted structural template of a chat page, not like a redrawn real screenshot.
The message bubble boundaries, time-divider positions, title bar edges, and input bar edges must be clear for later topology anchoring.
---END PROMPT---
```

### 10.1.4 基于已定义标准分区模板的做法

如果你已经有一张满意的聊天界面抽象底图，并且希望后续锚点拓扑严格围绕这张图展开，那么更好的方式不是继续让模型“理解分区”，而是直接把分区预先定义死。

建议将该底图视为固定模板，并明确以下结构区域：

1. `顶部导航区`
2. `状态栏`
3. `聊天标题`
4. `聊天标题栏右侧操作区`
5. `消息流主区`
6. `消息气泡组`
7. `时间分隔区`
8. `数据同步点`
9. `状态更新点`
10. `对端用户头像区`
11. `本端用户头像区`
12. `底部输入区`
13. `输入栏`
14. `功能按钮区`

这意味着：

1. Step A 已经完成，底图不再需要继续生成。
2. Step B 的任务变成：基于该模板的固定分区，生成“贴合结构的拓扑锚点机制图”。
3. 锚点位置应服从模板，而不是服从模型自由发挥。

### 10.1.5 基于该模板的区域约束规则

对于这张底图，建议直接规定以下锚点策略：

#### 主锚点候选区

1. 顶部导航区左右边界
2. 聊天标题中心区域
3. 时间分隔区标签
4. 大尺寸消息气泡组的外轮廓角点
5. 输入栏矩形边界

#### 辅锚点候选区

1. 对端头像外圆边界
2. 本端头像外圆边界
3. 单条消息气泡尾部或边角
4. 功能按钮区按钮边界
5. 状态更新点、小标签、局部留白结构边缘

#### 弱化区

1. 消息正文内部文本区域
2. 临时浮层或灰色占位块内容区
3. 高变化、低结构稳定性的内容填充区

原则是：

1. 主锚点优先挂在“稳定边界”和“几何中心特征”上。
2. 辅锚点优先挂在“局部修正有效、但不适合作为全局基准”的位置上。
3. 文本内容本身不应成为主锚点中心。

### 10.1.6 直接基于该底图生成完整机制图的提示词

下面这版提示词假设：

1. 你的聊天界面底图已经生成完成。
2. 分区名称和位置已经由你手工定义好。
3. 现在只需要模型在该模板之上生成“贴合分区的锚点拓扑机制图”。

```text
---BEGIN PROMPT---
[Style & Meta-Instructions]
Final academic mechanism figure for a GUI automation thesis, using the provided abstract mobile chat UI template as a fixed structural base. Do not redesign the UI layout. Preserve all predefined regions and place topology anchors according to those regions. Clean white background, strict 2D vector style, thesis-ready composition, no photorealism. All visible labels must be Chinese only.

[LAYOUT CONFIGURATION]
Selected Layout: Fixed mobile chat template with topology overlay
Composition Logic: keep the provided smartphone chat UI as the exact base structure. Overlay a sparse and stable topology graph that strictly follows the predefined regions and structural boundaries. Add a right-side legend if space allows, or keep the legend integrated in blank space around the figure.
Color Palette: dark blue for core anchors, light teal for auxiliary anchors, blue-gray for topology edges, pale orange or light gray for weakly used regions.

[FIXED BASE REGIONS]
The following regions are already defined and must be respected exactly:
"顶部导航区"
"状态栏"
"聊天标题"
"聊天标题栏右侧操作区"
"消息流主区"
"消息气泡组"
"时间分隔区"
"数据同步点"
"状态更新点"
"对端用户头像区"
"本端用户头像区"
"底部输入区"
"输入栏"
"功能按钮区"

[CORE ANCHOR PLACEMENT RULES]
Place core anchors only near:
"顶部导航区左右边界"
"聊天标题中心"
"时间分隔区标签"
"大消息气泡组外轮廓角点"
"输入栏矩形边界"

[AUXILIARY ANCHOR PLACEMENT RULES]
Place auxiliary anchors near:
"对端用户头像区边界"
"本端用户头像区边界"
"单条消息气泡边角"
"功能按钮区按钮边界"
"状态更新点"
"数据同步点"

[WEAK REGION RULES]
Weak or de-emphasized regions include:
"消息正文内部文本区域"
"灰色占位内容区"
"高变化局部内容区"
These regions may be lightly shaded but should not carry the main topology skeleton.

[LABEL RULES]
Use only short Chinese labels:
"主锚点"
"辅锚点"
"弱化区域"

[CONNECTIONS]
1. Connect core anchors into the main stable topology skeleton across the title area, message structure, and input area.
2. Connect auxiliary anchors only as local correction edges to nearby core anchors.
3. Keep the topology sparse and geometrically meaningful.
4. Avoid routing important edges through weak content regions.

[VISUAL EMPHASIS]
Anchor positions must visibly align with the predefined structural regions, not float randomly.
Core anchors must be larger, darker, and fewer.
Auxiliary anchors must be smaller, lighter, and clearly secondary.
The final image must look like a precise structural overlay on a fixed GUI template, not a freehand reinterpretation.
---END PROMPT---
```

### 10.1.7 更强约束版提示词

如果你的生图模型经常“偏题”，可以用下面这版更强硬的约束提示词：

```text
请严格以提供的聊天界面抽象图作为唯一结构模板，不允许改动界面布局，不允许新增无关模块，不允许重新解释分区。只允许在既有分区与既有边界上覆盖锚点、连线、弱化区域标记和图例。主锚点必须贴合顶部导航区、时间分隔区、大消息气泡组外轮廓和输入栏边界。辅锚点必须贴合头像边界、消息气泡边角、功能按钮边界和状态小标签。锚点不得漂浮在大块空白区域。所有图中文字必须为中文。
```

### 10.1.8 针对当前固定底图的最终完整提示词

下面这版提示词不再描述“通用聊天界面”，而是完全针对你当前这张抽象底图本身。  
原则上只做一件事：

1. 保留底图结构不变
2. 在固定位置生成主锚点和辅锚点
3. 用稀疏拓扑线把它们连起来
4. 将中部聊天内容主体视为动态噪音区或弱化区
5. 生成论文可用的机制图

```text
---BEGIN PROMPT---
[Style & Meta-Instructions]
Convert the provided abstract mobile chat UI base image into a thesis-ready mechanism figure for GUI automation. Use the provided image as a fixed template. Do not redesign the phone frame, do not change the layout, do not move the chat bubbles, avatars, separators, title area, or input bar. Only add anchor markers, topology edges, weak-region shading, and a concise legend. Clean white background, strict 2D vector style, academic software engineering figure, no photorealism, no extra decoration. All visible labels must be Chinese only.

[Global Objective]
Transform this fixed base image into a sparse topology anchor mechanism diagram. The topology must be attached to the predefined structural positions of the current image. The middle chat content region should be treated as a dynamic noisy region or weakly used region. The output must look like a precise structural overlay figure for a thesis, not like a new UI design.

[Fixed Base Structure - Must Remain Unchanged]
The following parts of the provided base image must stay exactly where they are:
1. Top phone frame and top white navigation bar
2. Back arrow at the top-left
3. Top-right three-dot action icon
4. Small rounded rectangular tag near the top center
5. Three green right-side bubbles in the upper half
6. Right-side circular avatar placeholders aligned with those bubbles
7. One long thin horizontal divider line in the upper-middle area
8. One left-side white bubble and left circular avatar in the middle area
9. One center dashed or striped separator tag in the middle-lower area
10. One green bubble on the right below the separator
11. One left white bubble and one lower right green bubble in the bottom half
12. Bottom input bar with voice icon, input box, emoji icon, and plus buttons

[Core Anchor Placement - Fixed Positions]
Place large dark-blue core anchors only at the following fixed control positions in the provided image:
1. Center of the top-left back button icon
2. Center of the top-right three-dot menu icon
3. Center of the bottom-left voice button icon
4. Center of the bottom-right emoji button icon
5. Center of the bottom-right plus button icon
6. Optional additional core anchor at the horizontal center of the input box, only if needed to stabilize the bottom interaction region

These core anchors are mandatory because they correspond to stable interactive controls with strong geometric identity and low layout ambiguity.

[Auxiliary Anchor Placement - Fixed Positions]
Place smaller light-teal auxiliary anchors only at the following fixed structural positions:
1. Centers of the visible avatar circles on the right side
2. Centers of the visible avatar circles on the left side
3. Tail corner of each visible green bubble
4. Outer corner of each visible white bubble
5. Left and right ends of the long horizontal divider line in the upper-middle area
6. Left and right ends of the striped separator tag in the middle-lower area
7. Left and right boundary corners of the input box

These auxiliary anchors may support local correction, but must not replace the main control-level core anchors.

[Weak Region Definition]
Mark the following region as a weak region or dynamic noisy region using a pale orange or pale gray translucent overlay:
1. The central chat-content area spanning the middle of the conversation stream
2. The internal text-bearing area inside all message bubbles
3. The broad blank conversational flow area between upper and lower message groups

This weak region must be visually de-emphasized and must not carry the main topology skeleton.

[Topology Connection Rules]
1. Connect the mandatory core anchors into one sparse stable skeleton from top navigation controls -> bottom interaction controls.
2. The main topology must form a clean polygonal or triangular sparse graph.
3. Auxiliary anchors may only connect to their nearest core anchors as local correction branches.
4. Do not draw dense mesh lines.
5. Do not route the main skeleton through the weak region center unless strictly necessary.
6. Topology lines should follow clear structural edges and control alignments, not float across empty space without reason.
7. The skeleton should visually express that the page can be stabilized by a small set of persistent controls, while the chat-content area remains weakly used.

[Labels - Chinese Only]
Use only the following concise labels if labels are shown:
"主锚点"
"辅锚点"
"弱化区域"
"稳定拓扑骨架"
"返回按钮"
"菜单按钮"
"语音按钮"
"表情按钮"
"加号按钮"

[Legend]
If there is enough blank space on the right side, add a small clean legend panel with three rows:
"主锚点：全局定位基准"
"辅锚点：局部修正依据"
"弱化区域：高变化内容"

If there is not enough space, place a compact legend below or in a corner without changing the phone layout.

[Visual Emphasis]
1. Core anchors must be visibly larger, darker, and fewer.
2. Auxiliary anchors must be smaller, lighter, and clearly secondary.
3. Weak region overlay must be semi-transparent and understated.
4. The final image must look like a structural annotation layer added onto the exact provided base image.
5. Do not add any new UI widgets, chat content, arrows, or labels beyond the mechanism explanation.
6. The back button, menu button, voice button, emoji button, and plus button must be immediately recognizable as the main anchor points.

[Negative Constraints]
Do not redesign the chat page.
Do not add new bubbles.
Do not rewrite message text.
Do not move avatars.
Do not create floating anchors in blank areas.
Do not make the topology too dense.
Do not use English text.
Do not place core anchors on message text bodies.
Do not treat the central conversation text area as the main structural skeleton.
---END PROMPT---
```

### 10.1.9 论文用图的人工校正规则

即便使用上面的强约束提示词，最终仍建议做一次人工校正。  
校正时只检查四件事：

1. 主锚点是否真的落在固定结构边界上。
2. 辅锚点是否只承担局部修正角色。
3. 中部聊天主体是否已经被明显弱化。
4. 拓扑线是否足够稀疏，没有遮挡关键结构。

#### Step B：基于底图生成论文最终机制图

目标：

1. 以 Step A 生成的聊天界面抽象底图为参考
2. 在顶部导航区、消息流主区、消息气泡组、底部输入区等关键位置生成锚点
3. 生成带锚点、图例和分区说明的完整机制图
2. 形成论文可用终稿图

建议内容：

1. 中间：聊天界面抽象底图与锚点拓扑
2. 右侧：图例面板
3. 图中标出“顶部导航锚点”“消息结构锚点”“输入区锚点”等语义
4. 对高动态、低稳定区域做弱化说明

建议提示词：

```text
---BEGIN PROMPT---
[Style & Meta-Instructions]
Final academic mechanism figure for a GUI automation thesis, using the previously generated abstract mobile chat UI as the structural reference, clean white background, strict 2D vector style, thesis-ready composition, no photorealism. All visible labels must be Chinese only.

[LAYOUT CONFIGURATION]
Selected Layout: Central smartphone topology figure with right-side legend panel
Composition Logic: based on the previously generated abstract mobile chat interface, overlay a sparse anchor topology graph on the top navigation zone, conversation structure, message bubble edges, time-divider labels, and bottom input area. A right-side legend explains core anchors, auxiliary anchors, and weakly used dynamic regions.
Color Palette: dark blue core anchors, light teal auxiliary anchors, pale orange dynamic region, light gray static skeleton, dark gray phone outline.

[ZONE 1: CENTER - 聊天界面与拓扑骨架]
Container: one centered smartphone frame
Visual Structure: stable abstract chat interface with title bar, message stream, left-right message bubbles, time-divider text, and bottom input bar; anchor graph overlaid on top
Key Text Labels:
"聊天标题栏"
"消息流区域"
"时间分隔区"
"输入栏"

[ZONE 2: OVERLAY - 锚点与连线]
Container: graph overlay inside the phone
Visual Structure: 3 to 4 core anchors and 5 to 7 auxiliary anchors connected into a sparse stable topology
Key Text Labels:
"主锚点"
"辅锚点"

[ZONE 3: WEAK REGION - 弱化区域]
Container: one or two semi-transparent highlighted patches
Visual Structure: pale orange translucent region covering highly variable message content or temporary floating elements, visually excluded from the core topology
Key Text Labels:
"弱化区域"

[ZONE 4: RIGHT - 图例说明面板]
Container: tall legend panel
Visual Structure: three legend rows with sample marker shapes and text
Key Text Labels:
"主锚点：主定位基准"
"辅锚点：局部修正依据"
"弱化区域：低稳定结构"

[CONNECTIONS]
1. Fine lines connecting anchors inside the phone.
2. Anchor positions must align with title bar corners, message bubble corners, time labels, and input bar corners.
3. One small explanatory arrow from the weak region toward the text "弱化".
3. Small callout arrows from the legend to corresponding visual markers if needed.

[VISUAL EMPHASIS]
The final figure must look clean, centered, and publication-ready.
Anchor positions must correspond to key chat-interface structures rather than random floating positions.
The topology must be obviously sparse and stable.
---END PROMPT---
```

### 10.2 进一步提高质量的建议

如果你使用的生图模型支持“参考图 / 图生图 / 局部重绘”，建议这样做：

1. 先用 Step A 生成手机界面骨架
2. 将 Step A 结果作为参考图输入
3. 再用 Step B 直接生成完整机制图

这样会显著提高：

1. 锚点落位准确度
2. 顶部导航区、消息流区、输入区的结构一致性
3. 锚点与聊天界面关键边界的贴合效果

### 10.3 如果只想最低成本地稳定出图

最稳的方法不是完全依赖一次生成，而是：

1. AI 先生成 Step A 的聊天界面抽象底图
2. 再以该底图为参考生成 Step B 完整机制图
3. 最后在 draw.io / PPT / Figma 中微调标签、线条和图例

这是当前最可控、最接近论文定稿质量的方式。
