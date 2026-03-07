# GUIAgent Contract v0（契约草案）

目标：定义 GUIAgent Phase 0 的最小统一协议，贯穿“大脑授权 -> 小脑执行 -> 反馈回灌”。

## 文档元信息

- 状态：`active`
- 版本：`v0.1`
- 更新时间：`2026-03-07`
- 适用阶段：`Phase 0`

## 1. 设计原则

1. 单一事实源：所有执行相关对象必须可序列化、可记录、可回放。  
2. 先兼容后替换：v0 支持映射现有 `{name, arguments}` 动作结构。  
3. 失败可解释：每次拒绝执行必须带结构化原因码。  
4. 默认保守：断言失败默认不执行，交给上层接管。

## 2. 核心对象

### 2.1 IntentKey

格式：
```text
<domain>:<verb>:<object>
```

示例：
- `global:TAP:SEARCH_BAR`
- `com.tencent.mm:TAP:SEND_BTN`
- `global:SWIPE:LIST_UP`

约束：
- `domain`：`global` 或应用标识（包名）。
- `verb`：`TAP|SWIPE|INPUT|LONG_PRESS|BACK|HOME|WAIT`。
- `object`：大写蛇形命名，描述动作对象。

### 2.2 IntentMetadata

```json
{
  "key": "global:TAP:SEARCH_BAR",
  "description": "点击搜索输入框",
  "aliases": ["搜索", "Search", "magnifier", "icon_hash:xxxx"],
  "risk_level": "LOW",
  "pre_conditions": ["PAGE_READY"],
  "post_expectations": ["KEYBOARD_VISIBLE"]
}
```

字段约束：
- `risk_level`：`LOW|MEDIUM|HIGH|CRITICAL`
- `aliases`：至少 1 个，用于执行前语义断言

### 2.3 ExecutionRequest

```json
{
  "request_id": "uuid",
  "intent_key": "global:TAP:SEARCH_BAR",
  "action": {
    "name": "Tap",
    "arguments": {"x": 520, "y": 180}
  },
  "assertion": {
    "expected_semantics": ["搜索", "Search"],
    "check_region": {"x": 460, "y": 120, "w": 180, "h": 120},
    "fail_policy": "HANDOVER_S2"
  },
  "timeout_ms": 3000,
  "retry_policy": {
    "max_retries": 2,
    "backoff_ms": 300
  }
}
```

字段约束：
- `fail_policy`：`BLOCK|RETRY_L1|RECOVER_L2|HANDOVER_S2`

### 2.4 ExecutionResult

```json
{
  "request_id": "uuid",
  "status": "SUCCESS",
  "assertion_result": {
    "passed": true,
    "reason_code": "OK"
  },
  "post_check": {
    "passed": true,
    "reason_code": "STATE_TRANSITION_OK"
  },
  "recovery_level": "NONE",
  "latency_ms": 540
}
```

状态枚举：
- `status`：`SUCCESS|FAILED|BLOCKED|HANDOVER`
- `recovery_level`：`NONE|L1|L2|L3`

### 2.5 BlueprintPatch（为 Phase 4 预留）

```json
{
  "patch_id": "uuid",
  "target_state": "global:PAGE:CHECKOUT",
  "version": "v0.1.0",
  "delta": {
    "anchors_updated": ["AUX_TAB_2"],
    "assertions_updated": ["global:TAP:PAY_BTN"]
  },
  "rollback_to": "v0.0.9"
}
```

## 3. 错误码与失败策略（v0）

错误码：
- `OK`
- `ASSERTION_MISMATCH`
- `TARGET_NOT_FOUND`
- `POST_CHECK_FAILED`
- `TIMEOUT`
- `UNKNOWN_ERROR`

策略映射：
- `ASSERTION_MISMATCH` -> `HANDOVER_S2`
- `TARGET_NOT_FOUND` -> `RETRY_L1`（最多 `max_retries`）
- `POST_CHECK_FAILED` -> `RECOVER_L2`
- `TIMEOUT` -> `HANDOVER_S2`

## 4. 与现有 Uni-Mind 的兼容映射

现有动作：
```json
{"name": "Tap", "arguments": {"x": 100, "y": 200}}
```

映射后：
```json
{
  "intent_key": "global:TAP:UNSPECIFIED_TARGET",
  "action": {"name": "Tap", "arguments": {"x": 100, "y": 200}}
}
```

说明：
- Phase 0 允许 `UNSPECIFIED_TARGET`，后续逐步收敛为标准对象名。

## 5. 版本规则

- `v0` 只允许新增可选字段，不允许删字段。  
- 破坏性变更进入 `v1`。  
- 每次契约升级必须附带迁移说明（old -> new 字段映射）。
