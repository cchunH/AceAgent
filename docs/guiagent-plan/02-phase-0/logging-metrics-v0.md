# GUIAgent Logging & Metrics v0（日志与指标口径）

目标：统一新旧链路的观测口径，使 Phase 0 可以做可信对照评估。

## 文档元信息

- 状态：`active`
- 版本：`v0.1`
- 更新时间：`2026-03-07`
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

## 3. 报告模板（每次 PoC 固定输出）

1. 实验上下文  
- 设备、分辨率、App 版本、网络条件

2. 指标对照表  
- `Success Rate / P50 / P95 / Takeover Rate / Retry Rate / Assertion Fail Rate`

3. 失败分布  
- 按 `reason_code` 排序统计

4. 关键样例  
- 选 3 个失败样例，附前后截图与事件链

## 4. 采样与统计规则

- 每个场景至少运行 30 次。  
- 统计窗口固定在同一设备和同一 App 版本。  
- 任何中途配置变更必须重新计入新实验批次。

## 5. 验收阈值（Phase 0 建议）

- 成功率：不低于旧链路基线（允许 ±2% 波动）  
- `P95`：不高于旧链路 +20%  
- `S2 Takeover Rate`：有下降趋势即可（Phase 0 不强卡绝对值）  
- 日志完整率：100%（关键字段不可缺失）
