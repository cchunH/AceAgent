# Phase 0 实验报告模板（GUIAgent）

> 用途：统一记录 `legacy` vs `guiagent_v2` 对照实验结果。

## 文档元信息

- 状态：`template`
- 版本：`v0.1`
- 更新时间：`2026-03-07`
- 适用阶段：`Phase 0`

## 1. 实验元信息

- 实验编号：  
- 日期：  
- 执行人：  
- 分支/提交：  
- 设备型号：  
- 分辨率：  
- 系统版本：  
- App 版本：  
- 网络条件：  

## 2. 实验配置

- 对照组 A：`legacy`  
- 对照组 B：`guiagent_v2`  
- 场景集：`A / B / C`（见 `poc-scenarios-v0.md`）  
- 每组运行次数：  
- 是否启用断言：  
- 是否启用 post-check：  

## 3. 指标结果（汇总表）

| 指标 | legacy | guiagent_v2 | 变化 |
|---|---:|---:|---:|
| Task Success Rate |  |  |  |
| Step Latency P50 (ms) |  |  |  |
| Step Latency P95 (ms) |  |  |  |
| S2 Takeover Rate |  |  |  |
| Retry Rate |  |  |  |
| Assertion Fail Rate |  |  |  |

## 4. 失败分布（reason_code）

| reason_code | legacy count | guiagent_v2 count | 备注 |
|---|---:|---:|---|
| ASSERTION_MISMATCH |  |  |  |
| TARGET_NOT_FOUND |  |  |  |
| POST_CHECK_FAILED |  |  |  |
| TIMEOUT |  |  |  |
| UNKNOWN_ERROR |  |  |  |

## 5. 关键样例复盘（至少 3 条）

### 样例 #1
- 场景：  
- 现象：  
- 事件链摘要：  
- 截图证据：  
- 原因判断：  
- 建议修复：  

### 样例 #2
- 场景：  
- 现象：  
- 事件链摘要：  
- 截图证据：  
- 原因判断：  
- 建议修复：  

### 样例 #3
- 场景：  
- 现象：  
- 事件链摘要：  
- 截图证据：  
- 原因判断：  
- 建议修复：  

## 6. 结论与决策

- 是否达成 Phase 0 DoD：`是 / 否`  
- 主要收益：  
- 主要问题：  
- 是否进入 Phase 1：`Go / No-Go`  
- 进入条件（若 No-Go）：  

## 7. 附录

- 原始日志路径：  
- 指标统计脚本路径：  
- 相关文档版本：  
- `contract-v0`：  
- `logging-metrics-v0`：  
- `poc-scenarios-v0`：  
