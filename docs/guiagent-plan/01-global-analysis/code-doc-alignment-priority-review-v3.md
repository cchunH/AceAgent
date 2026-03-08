# GUIAgent 代码-文档对齐与优先级评估 v3

## 文档元信息

- 状态：`active`
- 版本：`v3.0`
- 更新时间：`2026-03-08`
- 评估范围：
  - 代码：`guiagent_v2/*`, `run.py`, `test/*`
  - 文档：`integration-blueprint-v1.md`, `implementation-gap-and-reuse-plan-v2.md`, `post-r4-deep-assessment-and-next-plan-v2.md`

## 1. 结论摘要（先看）

1. 当前系统已达到“框架可运行 + 可观测 + 可扩展”的阶段。
2. 当前系统尚未达到“GUIAgent v2 独立功能完整可用”的阶段。
3. 最大阻断不在文档或控制面，而在执行主链：
- 移动端真实执行桥接已落地 v0（`auto|shadow|device`），但真实感知与多步循环仍未闭环。
- `guiagent_v2` 在 `--v2_skip_legacy` 下仍是单步 probe，不是完整任务循环。

## 2. 代码与文档对齐评估

## 2.1 一致项（文档和代码一致）

1. 运行时模式与并行孵化策略已落地
- 证据：`run.py`, `guiagent_v2/runtime/orchestrator_v2.py`
- 说明：`legacy | guiagent_v2_shadow | guiagent_v2` 与 `--v2_skip_legacy` 可用。

2. 观测链路已形成完整闭环
- 证据：`event_bus.py`, `event_schema.py`, `status_api.py`, `metrics.py`, `reporting.py`
- 说明：`events.jsonl -> metrics -> runtime_summary -> flow_audit` 已连通。

3. 控制面基础能力已可用于后续前端
- 证据：`session_runtime.py`, `session_runtime_server.py`
- 说明：会话、任务、时间线、审计、确认流接口已具备最小闭环。

4. 状态面算法 v0 已落地
- 证据：`scene_denoise.py`, `static_skeleton.py`, `topology_matcher.py`, `fast_match.py`
- 说明：动态去噪、骨架提取、主辅锚点评分、快速匹配都已进入主链。

## 2.2 偏差项（文档方向正确，但“可用定义”需下修）

1. “v2 可独立执行”在文档中仍需谨慎表述
- 证据：`guiagent_v2/runtime/mobile_device_executor.py`, `guiagent_v2/runtime/v2_executor.py`
- 现状：移动端已支持真实执行桥接，但真实任务仍受单步 probe 与合成感知输入限制。

2. “v2 主流程”在 `--v2_skip_legacy` 下仍是单步
- 证据：`guiagent_v2/runtime/orchestrator_v2.py:571-595`
- 现状：只调用一次 `run_probe_step(step_id=1)`，缺完整 planner/executor 循环。

3. “状态断言有效性”在纯 v2 下存在样本真实性不足
- 证据：`guiagent_v2/runtime/v2_executor.py:295-299`
- 现状：使用合成 `perception_infos_pre/post`，对真实场景泛化有限。

4. 向量检索虽已实现 mock，但尚未进入在线决策链
- 证据：`blueprint_hub/repository.py:191-224`
- 现状：`match_by_vector` 可用，但运行时未用于主链候选召回融合。

## 3. 完成度评估（按“功能完整可用”口径）

1. 架构与模块化：`82%`
2. 可观测与治理：`85%`
3. 控制面（会话/状态/API）：`80%`
4. 状态面算法（去噪/骨架/匹配）：`72%`
5. Web 旁路执行能力：`70%`
6. v2 独立执行闭环（不依赖 legacy）：`48%`
7. 综合完成度：
- 若允许 legacy 托底：`76%`
- 若要求 v2 独立闭环：`58%`

## 4. 优先级重排（以“功能完整可用”为目标）

## P0（阻断项，必须先做）

1. 移动端真实执行桥接（已完成 v0，需增强）
- 当前：已接入 `MobileDeviceExecutor`，支持 `auto|shadow|device` 与 ADB 不可用自动回退。
- 证据模块：`mobile_device_executor.py`, `pipeline.py`, `v2_executor.py`, `run.py`
- 剩余影响：仍缺真实感知输入联动与多步任务循环。
- 建议优先级：`P0-1`（剩余增强）

2. v2 多步任务主循环（非单步 probe）
- 当前：已落地“指令拆步 + `v2_max_steps` + handover 早停”的多步骨架。
- 证据模块：`orchestrator_v2.py`, `run.py`, `test/test_orchestrator_v2_loop.py`
- 剩余影响：仍缺“基于实时感知的动态子目标生成”，复杂任务完成率仍受限。
- 建议优先级：`P0-2`（剩余增强）

3. 真实感知接入 v2 断言链（替换合成 pre/post）
- 问题：断言输入不是设备真实帧。
- 证据模块：`v2_executor.py`, `assertion_guard.py`, `post_check.py`
- 影响：门控/微重试策略难以反映真实误触风险。
- 建议优先级：`P0-3`

4. v2 在线学习回灌（blueprint_sync）接入
- 问题：纯 v2 运行未回灌 blueprint。
- 证据模块：`orchestrator_v2.py`, `blueprint_sync.py`
- 影响：离线复盘和在线匹配难形成闭环增益。
- 建议优先级：`P0-4`

## P1（P0 完成后立刻推进）

1. 锚点门控阈值策略化（移出硬编码常量）
- 证据模块：`v2_executor.py` 中 `_CORE_ANCHOR_MIN_CONFIDENCE` 等常量。
- 目标：接入 policy/hook，支持分场景调参。

2. 向量召回融合到在线匹配链
- 证据模块：`repository.py`（已有 `match_by_vector`）。
- 目标：`skeleton + vector` 融合排序，提升模糊场景召回。

3. 确认流治理增强
- 证据模块：`status_api.py`, `session_runtime_server.py`
- 目标：批量确认、超时清理、恢复协议。

4. 长周期数据治理
- 目标：timeline 归档、审计聚合导出、跨文件查询。

## P2（后置）

1. 跨节点会话一致性（服务发现/租约）
2. Watchdog 扩展插件（download 等）
3. 群智联邦分发（继续后置，不进入当前主线）

## 5. 建议实施顺序（可直接开工）

1. R14（P0）：多步循环骨架 + 真实执行桥接（已完成 v0）
- 现状：骨架已落地并可配置 `v2_max_steps`。
- 剩余 DoD：接入实时感知驱动子目标更新，提升复杂任务可完成性。

2. R15（P0）：真实感知接入 + 在线回灌
- DoD：v2 路径产生真实 `perception` 驱动的 `assertion/post_check`，并更新 `blueprints.json`。

3. R16（P1）：阈值策略化 + 向量融合召回
- DoD：支持策略文件调参，离线回归显示误命中率下降。

4. R17（P1）：确认流与长期治理增强
- DoD：控制面可稳定管理长任务，无确认堆积与时间线失控。

## 6. Git 推进建议（保持现有节奏）

1. 每个 R 里程碑单独提交并打标签（`checkpoint/R14-*`）。
2. 每个提交必须“代码 + 测试 + 文档”三件套。
3. 固定回归命令：
- `python3 -m unittest discover -s test -p 'test_*.py'`
4. 保持 `legacy` 回退能力，直到 R15 通过后再讨论默认模式切换。

## 7. 这轮评估后的推荐

1. 不建议继续横向扩展新模块面。
2. 建议把接下来 1-2 轮全部投入 P0 阻断项。
3. 只有 P0 清空后，才算进入“GUIAgent v2 功能完整可用”阶段。
