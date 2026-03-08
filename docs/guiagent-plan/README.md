# GUIAgent 计划文档目录

本目录聚合 GUIAgent 蓝图评估与实施文档，作为 `Uni-Mind -> GUIAgent v2` 的专项工作区。

## 目录结构

```text
docs/guiagent-plan/
  README.md
  01-global-analysis/
  02-phase-0/
  03-governance/
  04-community-benchmark/
```

子目录索引：
- [01-global-analysis/README.md](./01-global-analysis/README.md)
- [02-phase-0/README.md](./02-phase-0/README.md)
- [03-governance/README.md](./03-governance/README.md)
- [04-community-benchmark/README.md](./04-community-benchmark/README.md)

## 1) 全局分析（01-global-analysis）

1. [guiagent-feasibility-report.md](./01-global-analysis/guiagent-feasibility-report.md)  
   可行性评估：按蓝图 01~11 分模块评估可落地性与风险。

2. [guiagent-gap-mapping-report.md](./01-global-analysis/guiagent-gap-mapping-report.md)  
   差距映射：GUIAgent 目标能力与现有 Uni-Mind 能力映射。

3. [guiagent-implementation-decision-report.md](./01-global-analysis/guiagent-implementation-decision-report.md)  
   实施决策：续迭代 vs 新开项目，推荐混合并行孵化方案。

4. [guiagent-roadmap-report.md](./01-global-analysis/guiagent-roadmap-report.md)  
   分阶段路线图：Phase 0~5 的目标、交付、验收。

5. [pre-recommendation-assessment-v1.md](./01-global-analysis/pre-recommendation-assessment-v1.md)  
   文档规范整理后的推荐前评估（Go/No-Go）。

6. [code-doc-practice-assessment-v1.md](./01-global-analysis/code-doc-practice-assessment-v1.md)  
   代码与文档实践细节评估（代码实现与文档规范一致性检查）。

7. [guiagent-refactor-recommendation-final-v1.md](./01-global-analysis/guiagent-refactor-recommendation-final-v1.md)  
   改造正式推荐与迁移说明（运行模式、快轨下线、控制面接入点）。

8. [post-r3-gap-review-and-next-plan-v1.md](./01-global-analysis/post-r3-gap-review-and-next-plan-v1.md)  
   R3/R4 实装后的差距审查与三轮迭代规划。

9. [post-r4-deep-assessment-and-next-plan-v2.md](./01-global-analysis/post-r4-deep-assessment-and-next-plan-v2.md)  
   新一轮代码-文档深度审查与 R5-R8 推进计划（治理硬化优先）。

10. [guiagent-blueprint-fidelity-review-v1.md](./01-global-analysis/guiagent-blueprint-fidelity-review-v1.md)  
   原始 GUIAgent 蓝图一致性复盘（流程复刻、偏移检查、向量检索接入建议）。

11. [code-doc-alignment-priority-review-v3.md](./01-global-analysis/code-doc-alignment-priority-review-v3.md)  
   最新代码-文档对齐审查与“功能完整可用”优先级重排（聚焦 v2 独立闭环阻断项）。

12. [blueprint-implementation-status-and-stable-validation-plan-v1.md](./01-global-analysis/blueprint-implementation-status-and-stable-validation-plan-v1.md)  
   最新蓝图执行现状、可用性评估、稳定实测版本（beta1）阶段计划与版本冻结策略。

## 2) 分阶段实施（02-phase-0）

1. [phase0-execution-checklist.md](./02-phase-0/phase0-execution-checklist.md)  
   下一步执行清单：Phase 0 的任务分解、验收标准与交付物模板。

2. [contract-v0.md](./02-phase-0/contract-v0.md)  
   Phase 0 契约草案：Intent/Execution/Result/Patch 的统一 schema。

3. [logging-metrics-v0.md](./02-phase-0/logging-metrics-v0.md)  
   统一日志与指标口径：用于 legacy 与 guiagent_v2 对照评估。

4. [poc-scenarios-v0.md](./02-phase-0/poc-scenarios-v0.md)  
   Phase 0 最小 PoC 场景集与验收标准。

5. [guiagent-v2-module-architecture-v0.md](./02-phase-0/guiagent-v2-module-architecture-v0.md)  
   `guiagent_v2` 模块架构草案与衔接方案。

6. [jsonl-log-samples-v0.md](./02-phase-0/jsonl-log-samples-v0.md)  
   JSONL 事件样例（成功/失败接管/legacy 映射）。

7. [phase0-experiment-report-template.md](./02-phase-0/phase0-experiment-report-template.md)  
   Phase 0 实验结果记录模板（可直接填报）。

8. [functional-first-task-allocation-r10-r13-v1.md](./02-phase-0/functional-first-task-allocation-r10-r13-v1.md)  
   功能优先任务分配（R10-R13，覆盖执行链、复盘回灌、检索层与控制面）。

9. [runtime-flow-code-audit-r10-v1.md](./02-phase-0/runtime-flow-code-audit-r10-v1.md)  
   R10 代码流程审查报告（按代码链路核对主流程实现与风险缺口）。

10. [anchor-selection-and-aux-anchor-thinking-v1.md](./02-phase-0/anchor-selection-and-aux-anchor-thinking-v1.md)  
   主辅锚点选择与辅助锚点作用思考文档（进入下一任务前的策略梳理）。

11. [stable-validation-runbook-v1.md](./02-phase-0/stable-validation-runbook-v1.md)  
   稳定实测运行手册（S1 前置检查、shadow/device 实测顺序、结果检查与故障定位）。

12. [stable-validation-tasks-v1.json](./02-phase-0/stable-validation-tasks-v1.json)  
   稳定实测最小任务集模板（5 个基线任务）。

13. [stable-validation-thresholds-v1.json](./02-phase-0/stable-validation-thresholds-v1.json)  
   稳定实测门禁阈值模板（用于运行后自动判定 PASS/WARN/FAIL）。

## 3) 治理规范（03-governance）

1. [documentation-standard-v1.md](./03-governance/documentation-standard-v1.md)  
   GUIAgent 文档规范（结构、命名、术语、冻结规则）。

## 4) 社区对标与复用（04-community-benchmark）

1. [agent-browser-deep-analysis.md](./04-community-benchmark/agent-browser-deep-analysis.md)  
   `agent-browser` 深度分析：IPC、协议校验、安全边界、快照与 diff 能力（用于 Web 旁路增强）。

2. [browser-use-deep-analysis.md](./04-community-benchmark/browser-use-deep-analysis.md)  
   `browser-use` 深度分析：Agent 循环、消息压缩、循环检测、工具注册、watchdog、会话服务。

3. [cross-project-tradeoff-and-patterns.md](./04-community-benchmark/cross-project-tradeoff-and-patterns.md)  
   两项目横向对比与选型矩阵。

4. [reusable-module-catalog-for-unimind.md](./04-community-benchmark/reusable-module-catalog-for-unimind.md)  
   面向 Uni-Mind 的 P0/P1/P2 可复用模块目录。

5. [integration-blueprint-v1.md](./04-community-benchmark/integration-blueprint-v1.md)  
   社区能力集成蓝图（接口草案 + 分阶段实施 + 退出条件，强调移动端主链优先）。

6. [skill-vs-modular-integration-decision.md](./04-community-benchmark/skill-vs-modular-integration-decision.md)  
   模式决策定稿：模块主线并入 + skill 旁路增强。

## 推荐阅读顺序

1. 先读 `01-global-analysis/*` 建立全局判断。
2. 再读 `02-phase-0/*` 进入执行。
3. 用 `04-community-benchmark/*` 形成外部能力复用清单。
4. 最后用 `03-governance/*` 约束文档与评审流程。
