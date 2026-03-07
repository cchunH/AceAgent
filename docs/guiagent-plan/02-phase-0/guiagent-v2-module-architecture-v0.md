# GUIAgent v2 模块架构草案（v0）

目标：给出 `guiagent_v2` 的最小可实现架构，支持 Phase 0~1 的并行孵化。

## 文档元信息

- 状态：`draft`
- 版本：`v0.1`
- 更新时间：`2026-03-07`
- 适用阶段：`Phase 0-1`

## 1. 目录建议

```text
guiagent_v2/
  intent_contract/
    schema.py
    mapper.py
  state_engine/
    anchor_extractor.py
    topology_matcher.py
  action_engine/
    affine_runtime.py
    assertion_guard.py
    post_check.py
  blueprint_hub/
    repository.py
    patch_model.py
  brain_adapter/
    planner_bridge.py
    executor_bridge.py
  runtime/
    orchestrator_v2.py
    event_logger.py
    feature_flags.py
```

## 2. 模块职责与接口

### 2.1 `intent_contract`

职责：
- 定义 `IntentKey`、`ExecutionRequest`、`ExecutionResult` 等 schema。
- 提供旧动作对象到新契约的兼容映射。

核心接口：
- `map_legacy_action_to_request(action_obj, context) -> ExecutionRequest`
- `validate_execution_request(req) -> ValidationResult`

### 2.2 `state_engine`

职责：
- 从感知结果中提取主辅锚点。
- 输出页面拓扑匹配置信度与候选坐标系。

核心接口：
- `extract_anchors(perception_infos, screen_size) -> list[AnchorNode]`
- `match_topology(anchors, blueprint_state) -> TopologyMatchResult`

### 2.3 `action_engine`

职责：
- 进行相对坐标到绝对坐标投射。
- 执行前语义断言与执行后状态确认。

核心接口：
- `project_action(req, topology_result) -> ProjectedAction`
- `run_pre_assertion(req, perception_infos) -> AssertionResult`
- `run_post_check(expected_state, current_state) -> PostCheckResult`

### 2.4 `blueprint_hub`

职责：
- 本地蓝图存储与版本管理。
- 预留补丁升级/回滚能力。

核心接口：
- `get_blueprint(intent_key, app_state) -> Blueprint | None`
- `save_blueprint(blueprint) -> None`
- `apply_patch(patch) -> PatchApplyResult`

### 2.5 `brain_adapter`

职责：
- 复用现有 Uni-Mind Planner/Executor 作为 System 2。
- 在 `guiagent_v2` 与现有 Agent 之间做协议桥接。

核心接口：
- `authorize_intent(context) -> IntentKey`
- `handover_to_s2(event) -> S2Decision`

### 2.6 `runtime`

职责：
- 编排一次完整执行链：授权 -> 拓扑 -> 断言 -> 执行 -> 后验 -> 记录。
- 管理 feature flag，支持灰度切换。

核心接口：
- `run_step(context) -> ExecutionResult`
- `run_task(task_spec) -> TaskResult`

## 3. 与现有 Uni-Mind 的衔接点

复用：
- 感知输入：`UniMind/perception/perceptor.py`
- 设备执行：`UniMind/device/action_executor.py` + `controller.py`
- 大脑能力：`UniMind/agents/expert_track_agents.py`

替换：
- 旧编排循环中的“动作决策后直接执行”分支，改为 `runtime/orchestrator_v2`。

## 4. Feature Flags（建议）

- `ENABLE_GUIAGENT_V2=false`（总开关）
- `ENABLE_PRE_ASSERTION=true`
- `ENABLE_POST_CHECK=true`
- `ENABLE_TOPOLOGY_MATCH=true`

说明：
- Phase 0 默认仅启用契约与日志；Phase 1 再开启拓扑与断言。

## 5. 实施顺序（最小闭环）

1. 先落 `intent_contract + runtime/event_logger`  
2. 再接 `brain_adapter + action_engine(assertion)`  
3. 最后接 `state_engine(topology)` 与 `blueprint_hub`

## 6. 当前落地进展（2026-03-07）

已落地：
- `intent_contract`：`ExecutionRequest/ExecutionResult` + legacy 映射
- `runtime`：`orchestrator_v2 + event_bus + status_api + metrics`
- `state_engine`：`anchor_extractor + topology_matcher`（规则型 MVP）
- `action_engine`：`assertion_guard + post_check + affine_runtime(占位投射)`
- `brain_adapter`：`planner_bridge + executor_bridge`（复用 Uni-Mind 既有 Agent）
- `blueprint_hub`：`repository + patch_model`（本地蓝图库 MVP，支持 patch）

待落地：
- `state_engine/action_engine` 从规则型升级为拓扑+语义联合判定
