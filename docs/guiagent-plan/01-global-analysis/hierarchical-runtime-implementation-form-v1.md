# GUIAgentV2 分层机制实现形态说明 v1

## 文档元信息

- 状态：`active`
- 版本：`v1.0`
- 更新时间：`2026-04-14`
- 适用范围：`runtime_mode=guiagent_v2`，重点覆盖 `--v2_skip_legacy` 主链
- 目标：用工程实现视角说明“这套机制现在是如何工作的”

## 1. 一句话定义

当前实现是“**分层规划 + 页面门禁 + 原子执行 + 事后回灌 + 双重验收**”的 GUI 自动化运行系统：
- 模型负责生成任务层级与纠偏决策；
- 执行器负责可控动作下发；
- 状态面负责页面一致性与断言；
- 回灌层负责把经验沉淀为蓝图；
- 审计与门禁负责防止假成功。

## 2. 运行链路（在线）

## 2.1 任务进入与分层计划

1. 用户指令进入 `orchestrator_v2`。
2. 在 `v2_skip_legacy` 路径下，调用 `model_task_planner` 生成计划：
- `steps[]`：可执行步骤文本。
- `subtasks[]`：子任务结构（`subtask_key/page_hint/page_fingerprint_id/match_threshold/goal_state/task_level`）。
3. 计划以事件 `model_task_plan` 落盘，便于复盘与门禁检查。

工程意义：
- 把复杂任务从“单步猜动作”提升为“多步可解释计划”。

## 2.2 子任务执行前页面门禁

每个 step 执行前，`v2_executor.run_probe_step` 会进行页面一致性检查：

1. 计算轻量命中证据：
- OCR 文本与 `page_hint` 匹配分（`fingerprint_match_score`）。
- `fast_match_hint`（蓝图检索信号）增强。

2. 计算拓扑证据：
- `topology_confidence/core_anchor_confidence/geometry_confidence`。

3. 融合为统一分数：
- `page_fingerprint_score`（融合评分）。

4. 指纹 ID 强校验：
- 对比 `expected_page_fingerprint_id` 与 `runtime_page_fingerprint_id`。

5. 门禁决策：
- 通过：继续执行。
- 不通过：直接 `HANDOVER`，并给出 `PAGE_HINT_MISMATCH` 或 `PAGE_FINGERPRINT_ID_MISMATCH`。

工程意义：
- 避免“错页误操作”，把风险前置到动作前。

## 2.3 原子动作执行与断言

通过门禁后进入动作执行：

1. `ActionRegistry` 路由到移动端执行（或 Web skill 路径）。
2. 执行后产生：
- `assertion`（前置语义/结构一致性）
- `post_check`（后置状态验证）
- `step_end`（步骤最终状态）

补充机制：
- `anchor_gate`：主/辅锚点置信度门控。
- `anchor_micro_retry`：局部重试。
- `assertion_repair`：复杂断言失败时可触发模型修复建议。

工程意义：
- 形成“动作不是完成，验证才是完成”的执行观。

## 2.4 复杂任务防退化

已实现“复杂任务单步 Wait 防假成功”：

1. 若复杂指令被模型退化成 `Wait`，触发 `intent_parse_guard`。
2. 任务不允许以该状态记为真实成功。
3. 流程审计会把“guard 后仍 SUCCESS”判为失败。

工程意义：
- 解决了历史上“看似成功、实际没做事”的核心质量问题。

## 3. 离线沉淀（回灌）

执行结束后，`blueprint_sync` 进行经验沉淀：

1. 提取并更新：
- 锚点
- 静态骨架
- 后置预期
- 回放质量分（replay quality）

2. Replay Gate 控制更新质量：
- 低质量样本可只更新元数据，抑制结构污染。

3. 页面绑定信息回写：
- `metadata.page_binding` 记录 `page_hint/page_fingerprint_id/runtime_page_fingerprint_id/match_threshold/page_fingerprint_score`。

工程意义：
- 在线执行结果能变成可复用知识，而不是一次性推理。

## 4. 可观测与验收机制

## 4.1 事件日志（`events.jsonl`）

关键事件：
- 规划：`model_task_plan`
- 门禁：`page_hint_gate`
- 退化保护：`intent_parse_guard`
- 执行：`adapter_call/assertion/post_check/step_end`
- 回灌：`blueprint_sync`
- 任务结束：`task_end`

## 4.2 双重质量门禁

1. `flow_audit`
- 检查事件序列完整性与语义一致性。
- 已包含规则：`intent_parse_guard` 与 `task_end=SUCCESS` 不可并存。

2. `validation_gate`
- 检查指标阈值与 `flow_audit_status`。
- 不是只看成功率，还看流程是否合法。

工程意义：
- “流程正确 + 指标达标”双条件，降低误判。

## 5. 当前实现边界（实事求是）

已完成：
1. 分层计划事件化（含 `subtasks` 元信息）。
2. 页面门禁（文本/拓扑/指纹 ID）与错页阻断。
3. 复杂任务 `Wait` 退化保护。
4. 回灌层写入页面绑定元数据。
5. preflight 依赖探针（含 `datasets` 关键符号兼容检查）。

仍在迭代：
1. `page_fingerprint_id` 从“运行时生成+计划传入”升级为“稳定仓内节点级主键体系”。
2. 复杂任务实机回归的规模化统计与阈值标定。
3. 渐进披露策略（L1/L2/L3 上下文下发）进一步产品化。

## 6. 对外使用建议（当前阶段）

1. 先跑 preflight/readiness，确认环境稳定。
2. 用复杂任务回归入口跑首轮 device 实测。
3. 同时查看：
- `runtime_summary.json`
- `events.jsonl`
- `blueprint_validation_gate` 报告
4. 若出现失败，优先按 `page_hint_gate -> assertion/post_check -> blueprint_sync` 顺序定位。

## 7. 结论

这套机制已经从“单步试探型执行”升级为“分层计划驱动、页面一致性约束、可回灌可审计”的运行形态。
在工程上，它具备进入稳定实测阶段的核心条件；接下来的重点是扩大复杂任务实测样本并完成阈值收敛。
