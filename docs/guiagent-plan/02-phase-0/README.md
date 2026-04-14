# 02 Phase 0

本目录存放 Phase 0 执行文档，目标是“契约与基线”落地。

## 文件

1. [phase0-execution-checklist.md](./phase0-execution-checklist.md)  
   执行清单与 DoD。

2. [contract-v0.md](./contract-v0.md)  
   契约草案（核心 schema）。

3. [logging-metrics-v0.md](./logging-metrics-v0.md)  
   日志与指标口径。

4. [jsonl-log-samples-v0.md](./jsonl-log-samples-v0.md)  
   JSONL 样例。

5. [poc-scenarios-v0.md](./poc-scenarios-v0.md)  
   对照场景设计。

6. [guiagent-v2-module-architecture-v0.md](./guiagent-v2-module-architecture-v0.md)  
   `guiagent_v2` 模块架构草案。

7. [phase0-experiment-report-template.md](./phase0-experiment-report-template.md)  
   实验报告模板。

8. [session-runtime-api-contract-v1.md](./session-runtime-api-contract-v1.md)  
   SessionRuntime 本地 HTTP IPC 接口契约（路径、鉴权、错误码）。

9. [functional-first-task-allocation-r10-r13-v1.md](./functional-first-task-allocation-r10-r13-v1.md)  
   功能优先任务分配（R10-R13，含向量检索接入时序）。

10. [runtime-flow-code-audit-r10-v1.md](./runtime-flow-code-audit-r10-v1.md)  
   R10 代码流程审查报告（主链完整性、状态机接入、测试证据与后续动作）。

11. [anchor-selection-and-aux-anchor-thinking-v1.md](./anchor-selection-and-aux-anchor-thinking-v1.md)  
   主辅锚点选择与辅助锚点作用思考（辅助定位、消歧、抗噪、恢复引导）。

12. [stable-validation-runbook-v1.md](./stable-validation-runbook-v1.md)  
   稳定实测运行手册（S1 前置检查、shadow/device 实测顺序、结果检查与故障定位）。

13. [stable-validation-tasks-v1.json](./stable-validation-tasks-v1.json)  
   稳定实测最小任务集模板（5 个基线任务）。

14. [stable-validation-thresholds-v1.json](./stable-validation-thresholds-v1.json)  
   稳定实测门禁阈值模板（供 `blueprint_validation_gate.py` 读取）。

15. [readiness-gate-execution-report-20260309.md](./readiness-gate-execution-report-20260309.md)  
   Readiness Gate 执行记录（基础链路 + 模型链路），用于判定是否可进入实测阶段。

16. [hierarchical-runtime-implementation-backlog-v1.md](./hierarchical-runtime-implementation-backlog-v1.md)  
   分层运行机制实施 Backlog（P0/P1、代码落位、测试清单、里程碑与回退策略）。

17. [stable-validation-complex-tasks-v1.json](./stable-validation-complex-tasks-v1.json)  
   复杂任务稳定实测任务集（WLAN、微信会话发送、备忘录到地图导航）。
