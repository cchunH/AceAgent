# GUIAgent PoC Scenarios v0（对照场景设计）

目标：为 Phase 0 提供“可重复、可对照、可量化”的最小场景集。

## 文档元信息

- 状态：`active`
- 版本：`v0.1`
- 更新时间：`2026-03-07`
- 适用阶段：`Phase 0`

## 1. 场景选择原则

1. 优先稳定页面：避免高动态推荐流。  
2. 路径短：3~6 步，便于定位问题。  
3. 可重复：同设备重复执行结果应一致。  
4. 可观察：每步都能定义明确的 pre/post 状态。

## 2. 场景集（v0）

### 场景 A：应用内搜索基础链路

流程（示意）：
1. 进入目标应用首页  
2. 点击搜索框（`global:TAP:SEARCH_BAR`）  
3. 输入关键词（`global:INPUT:SEARCH_TEXT`）  
4. 执行搜索（`global:TAP:SEARCH_SUBMIT`）  
5. 进入第一个结果（`global:TAP:RESULT_ITEM_1`）

对照目标：
- 验证 `IntentKey + Assertion + PostCheck` 主链是否可贯通。

### 场景 B：列表滚动与目标点击

流程（示意）：
1. 进入列表页  
2. 上滑一次（`global:SWIPE:LIST_UP`）  
3. 定位目标项并点击（`global:TAP:TARGET_ITEM`）  
4. 验证详情页打开（`global:PAGE:DETAIL`）

对照目标：
- 验证“动作后状态确认 + L1 重试”能力。

### 场景 C：异常干预（可选）

流程（示意）：
1. 在执行前人为触发弹窗/遮挡  
2. 执行目标点击  
3. 观察断言失败后是否触发 `L3 HANDOVER`

对照目标：
- 验证失败路径的结构化事件与接管逻辑。

## 3. 对照实验设计

对照组：
- `legacy`：现有 Uni-Mind 执行链  
- `guiagent_v2`：启用 Contract v0 + 断言事件记录链

控制变量：
- 同设备、同分辨率、同 App 版本  
- 同网络条件  
- 同场景执行次数（建议每组 30 次）

输出：
- 指标对照（见 `logging-metrics-v0.md`）  
- 失败类型分布  
- 关键样例截图与事件链

## 4. 验收标准（v0）

1. 功能验收
- 场景 A、B 均可完整跑通（至少 1 轮）。
- 关键事件（assertion/post_check/handover）可落盘。

2. 数据验收
- 同一场景、同组实验的日志结构一致。
- 每个失败步骤都具备 `reason_code`。

3. 质量验收
- `guiagent_v2` 成功率不显著劣化（相对 `legacy`）。
- 至少有一项指标出现正向趋势（如 `S2 Takeover Rate` 或 `Retry Rate`）。

## 5. 首轮执行建议

优先顺序：
1. 场景 A（最先）  
2. 场景 B（其次）  
3. 场景 C（最后）

原因：
- A 能最早验证“契约可用性”；
- B 验证“执行鲁棒性”；
- C 验证“异常可解释性”。
