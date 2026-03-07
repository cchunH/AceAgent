# Skill 引入 vs 模块拆解并入：决策报告（移动端场景）

## 文档元信息

- 状态：`active`
- 版本：`v1.0`
- 更新时间：`2026-03-07`
- 决策范围：`guiagent_v2` 下一阶段架构演进

## 1. 决策问题

在移动端主场景下，Web 执行能力要以什么方式接入更可控、更健康：

1. 方案 A：以 `AgentBrowserSkill` 为主，快速引入外部能力。
2. 方案 B：以模块拆解并入为主（`ActionRegistry/GuardPolicy/SessionRuntime/WebSkillRouter`），`skill` 作为辅线。

## 2. 对比结论

| 维度 | 方案 A（Skill 主导） | 方案 B（模块主导 + Skill 辅助） |
|---|---|---|
| 初期速度 | 高 | 中 |
| 可控性 | 中低 | 高 |
| 可观测一致性 | 中 | 高 |
| 长期维护成本 | 高 | 中低 |
| 移动端能力边界稳定性 | 中低 | 高 |
| 架构健康度 | 中 | 高 |

结论：选 `方案 B`。

## 3. 推荐模式（最终）

`模块拆解并入（主线） + AgentBrowserSkill（辅线）`

1. `mobile_native` 是默认主通道。
2. `web_skill` 是能力增强旁路，仅处理网页子任务。
3. skill 失败必须回退主链，且回退可观测、可审计。

## 4. 为什么更健康

1. 责任边界清晰：移动端系统动作与 Web 自动化不混线。
2. 接口先行：通过 `WebSkillRouter` 与 `GuardPolicy` 保证执行决策可解释。
3. 可演进：后续无论替换 `agent-browser` 还是内建 Web 引擎，都不影响主编排契约。
4. 回归风险低：核心链路稳定，新增能力只影响旁路。

## 5. 实施守则（必须）

1. 禁止把设备系统动作路由到 `web_skill`。
2. 禁止无事件审计的 skill 调用。
3. 禁止把 `skill` 结果直接写入全局状态而不经过契约校验。
4. 禁止在未完成 fallback 验收前默认启用 `web_skill`。

## 6. 验收门槛（Go/No-Go）

1. `mobile_native_coverage = 100%`（系统动作场景）。
2. `web_skill_route_precision >= 95%`。
3. `web_skill_fallback_success_rate >= 90%`。
4. 核心移动端场景成功率不低于改造前基线。

## 7. 与现有文档关系

1. 该决策为 `integration-blueprint-v1.md` 的执行前置结论。
2. 该决策与 `reusable-module-catalog-for-unimind.md` 的 P0/P1/P2 优先级一致。
3. 若后续出现与本决策冲突的改造方案，以本文件为准并发起版本升级评审。
