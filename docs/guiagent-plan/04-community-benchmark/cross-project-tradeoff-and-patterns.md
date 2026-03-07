# agent-browser vs browser-use：横向权衡与复用模式

## 文档元信息

- 状态：`active`
- 版本：`v1.0`
- 更新时间：`2026-03-07`
- 结论导向：服务 `guiagent_v2` 的模块化改造，而非另起炉灶

## 1. 对比总览

| 维度 | agent-browser | browser-use | 对 Uni-Mind 的意义 |
|---|---|---|---|
| 核心定位 | 浏览器执行引擎 | 端到端 Agent 框架 | 可形成“执行内核 + 智能编排”组合 |
| 技术栈 | TS + Rust + Playwright | Python + CDP + EventBus | 直接融入 Uni-Mind 更偏 browser-use 风格 |
| 启动性能 | 强（native CLI + daemon） | 强（轻 CLI + server） | 两者都提供会话常驻模式参考 |
| 安全治理 | 强（policy/domain/origin） | 中高（事件治理、配置控制） | agent-browser 在安全边界更即插即用 |
| 插件化 | 中（动作丰富但中心化） | 强（Registry + Tools） | browser-use 更适合扩展动作生态 |
| 可观测性 | 中高（命令结果、流式） | 高（事件、telemetry、state） | browser-use 模式更适合控制面 |
| 迁移成本到 Uni-Mind | 中高（跨语言） | 中（同 Python） | 应优先 Python 侧吸收，再外接 agent-browser |
| 移动端适配性 | 低（偏 Web 执行） | 中（可编排多通道） | 必须由 Uni-Mind 主链承担移动端系统动作 |

## 2. 关键权衡

## 2.1 可靠性 vs 效率

- agent-browser 倾向“执行可靠性 + 命令效率”，强调协议边界与安全拦截。
- browser-use 倾向“任务闭环可靠性”，通过循环检测、watchdog 和 message compaction 控制长流程失败。

建议：
- 执行层借鉴 agent-browser 的硬门禁。
- 决策/长链路层借鉴 browser-use 的软纠偏。

## 2.2 可解释性 vs 复杂度

- agent-browser 的命令-响应路径相对直接，可解释性高。
- browser-use 的事件驱动和多层抽象带来更强能力，但复杂度显著增加。

建议：
- `guiagent_v2` 先保持流程直观，再逐步引入事件化 watchdog。

## 2.3 通用性 vs 专项优化

- agent-browser 对“Web 自动化执行”专项优化明显。
- browser-use 对“通用 Agent 任务编排”更有延展性。

建议：
- 将两者拆成两个适配层：
  - `WebAutomationAdapter`（偏 agent-browser）
  - `ActionRegistry/SessionRuntime`（偏 browser-use）

## 2.4 安全治理 vs 灵活度

- agent-browser 的 policy/domain 限制会降低灵活度，但非常适合企业环境。
- browser-use 偏开发友好，默认限制较少。

建议：
- 生产模式默认启用 stricter policy。
- 研发模式允许放宽并记录审计日志。

## 2.5 移动端场景修正（关键）

- 本项目是移动端主场景，`agent-browser` 只能增强 Web 子任务，不能替代 ADB 原生动作链。
- 移动端任务常见关键路径（权限弹窗、系统输入法、应用切换、返回栈）不适合走浏览器执行器。
- 推荐双通道执行模型：
  - `mobile_native`：当前 Uni-Mind 原生链路（默认）
  - `web_skill`：通过 skill 调用 agent-browser，处理 H5/网页子任务

## 3. 复用模式矩阵（什么时候选谁）

| 场景 | 优先选择 | 原因 | 备选 |
|---|---|---|---|
| 需要强安全边界的 Web 执行 | agent-browser 模式 | action policy + domain filter + origin 限制完备 | browser-use + 自建安全层 |
| 需要快速扩展动作工具生态 | browser-use 模式 | Registry + Tools 扩展模型成熟 | 自建 registry |
| 需要长任务稳定运行 | browser-use 模式 | message compaction + loop detector + watchdog | 现有 Uni-Mind + 补丁增强 |
| 需要高性能命令式自动化 | agent-browser 模式 | native CLI + daemon IPC 成熟 | browser-use skill_cli |
| 需要可控引入外部能力 | 混合模式 | Python 主编排 + agent-browser 外部适配器 | 单一方案 |
| 移动端系统动作（App/ADB） | Uni-Mind 原生链 | 设备控制能力与系统状态依赖重 | 不建议用 agent-browser 替代 |
| 移动端内 H5/网页子流程 | `web_skill` 混合模式 | 在不破坏主链下增强 Web 执行能力 | 人工接管 |

## 4. 推荐的混合架构（服务 guiagent_v2）

1. `guiagent_v2` 作为主编排。
2. 吸收 browser-use 的三类机制：
- 上下文压缩（MessageManager 思路）
- 循环检测（ActionLoopDetector 思路）
- 动作注册中心（Registry 思路）
3. 通过 `WebAutomationAdapter` 外接 agent-browser：
- 接入 `snapshot/diff/policy/domain/stream` 等执行能力。
- 以 `AgentBrowserSkill` 形式挂到 skill 层，由路由器判定是否调用。
4. 统一事件总线：
- 映射 `task_start/step_start/action_exec/assertion/post_check/handover/step_end/task_end`。
- 额外记录 `channel=mobile_native|web_skill`。

## 5. 风险与防护

1. 风险：跨语言外部进程接入导致调试复杂。
- 防护：先落本地单进程 mock adapter，再接真实 agent-browser adapter。

2. 风险：复用过快造成接口失稳。
- 防护：先冻结 `WebAutomationAdapter/ActionRegistry/GuardPolicy/SessionRuntime` 草案。

3. 风险：过度引入 browser-use 复杂度。
- 防护：P0 仅引入 loop/compaction/session 模式，不引入全量事件生态。

4. 风险：Web 能力侵入主链，导致移动端动作回归。
- 防护：固定路由白名单，只有 `web:*` intent 或显式 `web_skill` 任务才可进入旁路。

## 6. 结论

对 Uni-Mind 最优策略不是二选一，而是“Python 主线吸收 browser-use 的编排优势 + 外接 agent-browser 的执行治理能力”。这一路径最符合当前 `guiagent_v2` 已有结构，也最利于分阶段落地。

## 7. 推荐落地次序（理顺版）

1. 先做模块化主线：`ActionRegistry + GuardPolicy + SessionRuntime`。
2. 再接 `WebSkillRouter`：明确 mobile/web 双通道路由。
3. 最后接 `AgentBrowserSkill`：仅给 Web 子任务提速，不替代移动端主链。
