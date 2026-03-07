# JSONL 日志样例（Phase 0 / v0）

目标：提供可直接落地的事件样例，保障新旧链路对照统计的一致性。

## 文档元信息

- 状态：`active`
- 版本：`v0.1`
- 更新时间：`2026-03-07`
- 适用阶段：`Phase 0`

## 1. 事件序列（成功路径）

```json
{"ts":"2026-03-07T13:00:00.100Z","run_id":"run_001","task_id":"task_search_01","step_id":1,"chain_mode":"guiagent_v2","event_type":"step_start","intent_key":"global:TAP:SEARCH_BAR","status":"RUNNING"}
{"ts":"2026-03-07T13:00:00.180Z","run_id":"run_001","task_id":"task_search_01","step_id":1,"chain_mode":"guiagent_v2","event_type":"assertion","intent_key":"global:TAP:SEARCH_BAR","assertion_result":{"passed":true,"reason_code":"OK"},"recovery_level":"NONE","s2_takeover":false}
{"ts":"2026-03-07T13:00:00.240Z","run_id":"run_001","task_id":"task_search_01","step_id":1,"chain_mode":"guiagent_v2","event_type":"action_exec","intent_key":"global:TAP:SEARCH_BAR","action":{"name":"Tap","arguments":{"x":520,"y":180}},"retry_count":0,"timeout_ms":3000}
{"ts":"2026-03-07T13:00:00.520Z","run_id":"run_001","task_id":"task_search_01","step_id":1,"chain_mode":"guiagent_v2","event_type":"post_check","intent_key":"global:TAP:SEARCH_BAR","post_check":{"passed":true,"reason_code":"KEYBOARD_VISIBLE"}}
{"ts":"2026-03-07T13:00:00.530Z","run_id":"run_001","task_id":"task_search_01","step_id":1,"chain_mode":"guiagent_v2","event_type":"step_end","intent_key":"global:TAP:SEARCH_BAR","status":"SUCCESS","latency_ms":430}
```

## 2. 事件序列（断言失败 -> S2 接管）

```json
{"ts":"2026-03-07T13:01:00.100Z","run_id":"run_002","task_id":"task_search_01","step_id":2,"chain_mode":"guiagent_v2","event_type":"step_start","intent_key":"global:TAP:SEARCH_SUBMIT","status":"RUNNING"}
{"ts":"2026-03-07T13:01:00.180Z","run_id":"run_002","task_id":"task_search_01","step_id":2,"chain_mode":"guiagent_v2","event_type":"assertion","intent_key":"global:TAP:SEARCH_SUBMIT","assertion_result":{"passed":false,"reason_code":"ASSERTION_MISMATCH","expected_semantics":["搜索","Search"]},"recovery_level":"L3","s2_takeover":true}
{"ts":"2026-03-07T13:01:00.181Z","run_id":"run_002","task_id":"task_search_01","step_id":2,"chain_mode":"guiagent_v2","event_type":"handover","intent_key":"global:TAP:SEARCH_SUBMIT","status":"HANDOVER","handover_target":"SYSTEM_2","reason_code":"ASSERTION_MISMATCH"}
{"ts":"2026-03-07T13:01:01.000Z","run_id":"run_002","task_id":"task_search_01","step_id":2,"chain_mode":"guiagent_v2","event_type":"step_end","intent_key":"global:TAP:SEARCH_SUBMIT","status":"HANDOVER","latency_ms":900}
```

## 3. 任务结束事件

```json
{"ts":"2026-03-07T13:01:05.000Z","run_id":"run_002","task_id":"task_search_01","chain_mode":"guiagent_v2","event_type":"task_end","status":"SUCCESS","summary":{"steps":5,"handover_count":1,"retry_steps":1}}
```

## 4. legacy 链路映射样例

```json
{"ts":"2026-03-07T13:02:00.100Z","run_id":"run_legacy_01","task_id":"task_search_01","step_id":1,"chain_mode":"legacy","event_type":"step_end","intent_key":"global:TAP:UNSPECIFIED_TARGET","status":"SUCCESS","latency_ms":700}
```

说明：
- `legacy` 至少要补齐 `chain_mode/step_id/status/latency_ms/intent_key` 五个关键字段。

## 5. 字段完整性检查清单

每条日志至少包含：
- `ts`
- `run_id`
- `task_id`
- `chain_mode`
- `event_type`
- `status`（对 `step_start` 可填 `RUNNING`）

对 `step_end` 额外要求：
- `step_id`
- `latency_ms`
- `intent_key`
