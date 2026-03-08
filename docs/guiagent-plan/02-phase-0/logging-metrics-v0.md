# GUIAgent Logging & Metrics v0（日志与指标口径）

目标：统一新旧链路的观测口径，使 Phase 0 可以做可信对照评估。

## 文档元信息

- 状态：`active`
- 版本：`v0.4`
- 更新时间：`2026-03-08`
- 适用阶段：`Phase 0`

## 1. 日志格式

推荐使用 JSONL（每行一个事件）。

### 1.1 通用字段

```json
{
  "ts": "2026-03-07T12:34:56.789Z",
  "run_id": "uuid",
  "task_id": "string",
  "step_id": 12,
  "chain_mode": "legacy|guiagent_v2",
  "event_type": "step_start|assertion|action_exec|post_check|step_end|handover",
  "intent_key": "global:TAP:SEARCH_BAR",
  "status": "SUCCESS|FAILED|BLOCKED|HANDOVER",
  "latency_ms": 123
}
```

### 1.2 执行断言事件

```json
{
  "event_type": "assertion",
  "assertion_result": {
    "passed": false,
    "reason_code": "ASSERTION_MISMATCH",
    "expected_semantics": ["搜索", "Search"]
  },
  "recovery_level": "L3",
  "s2_takeover": true
}
```

### 1.3 动作执行事件

```json
{
  "event_type": "action_exec",
  "action": {"name": "Tap", "arguments": {"x": 500, "y": 200}},
  "retry_count": 1,
  "timeout_ms": 3000
}
```

## 2. 指标定义（冻结口径）

### 2.1 Task Success Rate

定义：
```text
成功任务数 / 总任务数
```

任务成功标准：
- 最终 `task_end.status == SUCCESS`

### 2.2 Step Latency（P50/P95）

定义：
```text
step_end.ts - step_start.ts
```

统计：
- 每个场景分别统计 `P50/P95`
- 对照 `legacy` 与 `guiagent_v2` 两组

### 2.3 S2 Takeover Rate

定义：
```text
发生 handover 事件的步骤数 / 总步骤数
```

解读：
- 越低代表“编译执行”占比越高（前提是成功率不下降）

### 2.4 Retry Rate

定义：
```text
retry_count > 0 的步骤数 / 总步骤数
```

解读：
- 过高说明状态面或动作面稳定性不足

### 2.5 Assertion Fail Rate（新增）

定义：
```text
assertion_result.passed == false 的步骤数 / 有断言步骤数
```

### 2.6 Denoise Stable Ratio（新增）

定义：
```text
每步去噪后稳定特征数 / (稳定特征数 + 动态特征数)
```

字段来源：
- `assertion_result.denoise_stable_ratio`
- `post_check.denoise_stable_ratio`

解读：
- 越高表示当前页面结构越稳定。
- 长期低值通常意味着动态噪声过高或 OCR 抖动明显。

### 2.7 Skeleton Match Confidence（新增）

定义：
```text
静态骨架匹配置信度（0~1）
```

字段来源：
- `assertion_result.skeleton_confidence`
- `post_check.skeleton_confidence`

解读：
- 可作为结构断言和状态迁移判定的辅助信号。
- 建议与 `topology_confidence` 联合观察。

### 2.8 Fast Match Hit / Score（新增）

定义：
```text
fast_match 命中次数 / 总匹配尝试次数
```
与
```text
fast_match score 的 P50/P95
```

字段来源：
- `assertion.fast_match_hint.matched_score`
- `assertion.fast_match_hint.signature_hit`

解读：
- 用于衡量在线快速匹配（blueprint 检索）效果。
- 低命中率说明骨架索引质量或场景稳定性不足。

### 2.9 Offline Replay Rebuild Coverage（新增）

定义：
```text
离线复盘重建成功动作数 / 可复盘动作总数
```

字段来源（离线任务输出）：
- `rebuilt_count`
- `skipped_count`
- `total_blueprints`

### 2.10 Anchor Gate / Micro-Retry（新增）

定义：
```text
anchor_gate_allow/retry/deny 占比 + micro_retry 的 applied/success/recovered 占比
```

字段来源：
- `event_type=anchor_gate`：`anchor_gate_decision`
- `event_type=anchor_micro_retry`：`anchor_retry_applied` 与 `status`

解读：
- `anchor_gate_deny_rate` 高：主锚点稳定性不足，容易触发阻断。
- `anchor_gate_retry_rate` 高且 `anchor_micro_retry_recovered_rate` 低：辅锚点重试收益不足，需优化辅助定位策略。
- `anchor_micro_retry_applied_rate` 与 `anchor_micro_retry_success_rate` 可用于评估“重试是否有效”。

### 2.11 Topology Projection Guard（新增）

定义：
```text
topology_projection_affine/scale 占比 + guard_block 占比 + fit_error P50/P95
```

字段来源：
- `event_type=topology_projection`
- `projection_mode=affine_norm|scale`
- `projection_guard_reason=OK|INSUFFICIENT_ANCHOR_PAIRS|AFFINE_FIT_ERROR_HIGH|CORE_CONFIDENCE_LOW|NO_AFFINE_TRANSFORM`
- `transform_fit_error`

解读：
- `topology_projection_affine_rate` 高：锚点几何质量足以支撑仿射迁移。
- `topology_projection_guard_block_rate` 高：当前场景锚点质量不足，系统大量回退为缩放策略。
- `topology_projection_fit_error_p95` 高：需要收紧蓝图锚点质量或调整多帧去噪参数。

### 2.12 Screenshot Trace Coverage（新增）

定义：
```text
snapshot_with_path_rate + mobile_action_screenshot_rate
```

字段来源：
- `event_type=snapshot_captured`：`snapshot_path`
- `event_type=adapter_call`（`adapter_backend=mobile-*`）：`screenshot_path`

解读：
- `snapshot_with_path_rate` 低：live perception 快照未稳定落盘。
- `mobile_action_screenshot_rate` 低：移动执行动作截图留痕不完整（常见于 adb 不可用或路径权限问题）。

## 3. 报告模板（每次 PoC 固定输出）

1. 实验上下文  
- 设备、分辨率、App 版本、网络条件

2. 指标对照表  
- `Success Rate / P50 / P95 / Takeover Rate / Retry Rate / Assertion Fail Rate / Denoise Stable Ratio / Skeleton Confidence / Fast Match Hit`

3. 失败分布  
- 按 `reason_code` 排序统计

4. 关键样例  
- 选 3 个失败样例，附前后截图与事件链

5. 复盘附录（新增）
- `offline replay` 重建统计
- 典型 `fast_match` 命中/误命中样例

## 4. 采样与统计规则

- 每个场景至少运行 30 次。  
- 统计窗口固定在同一设备和同一 App 版本。  
- 任何中途配置变更必须重新计入新实验批次。

## 5. 验收阈值（Phase 0 建议）

- 成功率：不低于旧链路基线（允许 ±2% 波动）  
- `P95`：不高于旧链路 +20%  
- `S2 Takeover Rate`：有下降趋势即可（Phase 0 不强卡绝对值）  
- 日志完整率：100%（关键字段不可缺失）
- `Denoise Stable Ratio`：核心场景建议 `>= 0.55`
- `Skeleton Match Confidence`：关键路径建议 `P50 >= 0.6`
- `Topology Projection Guard Block Rate`：关键路径建议 `<= 0.25`
