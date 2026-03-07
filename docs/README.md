# Uni-Mind 项目分析文档

本目录用于梳理 Uni-Mind 的架构、流程和设计决策，基于当前仓库代码（`run.py`、`orchestrator.py`、`UniMind/`）整理。

## 文档索引

1. [deep-system-audit-report.md](./deep-system-audit-report.md)  
   深度审计总报告（一次性阅读版），覆盖系统边界、架构、Agent 决策链、风险分级与改造路线。

2. [project-overview.md](./project-overview.md)  
   项目定位、核心能力、分层架构、关键对象。

3. [execution-flow.md](./execution-flow.md)  
   从入口到任务结束的端到端执行流程，包括专家轨与可选快轨。

4. [module-design.md](./module-design.md)  
   各模块职责、输入输出、关键实现细节（Agent/感知/设备/API）。

5. [config-and-ops.md](./config-and-ops.md)  
   配置项、运行模式、日志产物、常用启动方式。

6. [agent-architecture-deep-dive.md](./agent-architecture-deep-dive.md)  
   Agent 架构深潜：职责边界、输入输出契约、协作协议、风险点。

7. [system-tradeoff-analysis.md](./system-tradeoff-analysis.md)  
   关键设计权衡：可靠性/效率、可解释性/灵活性、通用性/专项优化等。

8. [module-locator-index.md](./module-locator-index.md)  
   模块级定位索引：入口、上游依赖、下游影响、故障入口、观测信号。

9. [risks-and-improvements.md](./risks-and-improvements.md)  
   当前实现中的风险点与建议优化方向（按优先级）。

## GUIAgent 专题报告

1. [guiagent-plan/README.md](./guiagent-plan/README.md)  
   GUIAgent 专项目录索引（建议从这里进入）。

2. [guiagent-feasibility-report.md](./guiagent-plan/01-global-analysis/guiagent-feasibility-report.md)  
   GUIAgent 蓝图可行性评估（按 01~11 模块给出可行性与风险）。

3. [guiagent-gap-mapping-report.md](./guiagent-plan/01-global-analysis/guiagent-gap-mapping-report.md)  
   GUIAgent 目标能力与现有 Uni-Mind 模块差距映射。

4. [guiagent-implementation-decision-report.md](./guiagent-plan/01-global-analysis/guiagent-implementation-decision-report.md)  
   实施决策：续迭代 vs 新开项目，含推荐方案与 Go/No-Go 门槛。

5. [guiagent-roadmap-report.md](./guiagent-plan/01-global-analysis/guiagent-roadmap-report.md)  
   分阶段落地路线图、验收标准、风险与资源建议。

6. [phase0-execution-checklist.md](./guiagent-plan/02-phase-0/phase0-execution-checklist.md)  
   Phase 0 执行清单（契约、日志指标、PoC 验收）。

7. [code-doc-practice-assessment-v1.md](./guiagent-plan/01-global-analysis/code-doc-practice-assessment-v1.md)  
   代码与文档实践细节评估（推荐前质量审计）。

8. [guiagent-refactor-recommendation-final-v1.md](./guiagent-plan/01-global-analysis/guiagent-refactor-recommendation-final-v1.md)  
   GUIAgent 改造正式推荐与迁移说明。

9. [community benchmark](./guiagent-plan/04-community-benchmark/README.md)  
   社区标杆项目深度对标（agent-browser + browser-use）与复用落地蓝图（移动端主链优先，Web skill 旁路增强）。

## 推荐阅读顺序

1. `deep-system-audit-report`（先建立全局认知）
2. `project-overview` + `execution-flow`（对齐系统主路径）
3. `agent-architecture-deep-dive` + `module-design`（深入设计细节）
4. `module-locator-index`（用于排障与代码定位）
5. `system-tradeoff-analysis` + `risks-and-improvements`（用于评审与改造）
