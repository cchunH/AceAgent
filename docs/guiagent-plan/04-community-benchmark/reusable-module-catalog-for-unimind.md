# Uni-Mind 可复用模块目录（来自 agent-browser + browser-use）

## 文档元信息

- 状态：`active`
- 版本：`v1.0`
- 更新时间：`2026-03-07`
- 目的：为 `guiagent_v2` 改造提供可执行模块清单（P0/P1/P2）

## 优先级定义

- `P0`：高价值、低改造成本，建议优先进入实现。
- `P1`：中等价值或中等改造成本，需 adapter 或模块重构。
- `P2`：高价值但高成本，建议后置。

## 移动端约束总则（新增）

1. `agent-browser` 只作为 Web 子任务增强能力，不替代移动端 ADB 主链。
2. 任何系统级移动端动作（`Open_App/Back/Home/Switch_App/Type` 等）必须走 `mobile_native`。
3. Skill 接入时必须显式标注通道与回退策略：`channel=web_skill`, `fallback=mobile_native`。
4. 所有 `web_skill` 执行必须落事件字段：`channel`, `skill_name`, `route_reason`。

## P0 清单

## P0-1 行为循环探测器

- 来源模块：`demo/browser-use/browser_use/agent/views.py` (`ActionLoopDetector`, `PageFingerprint`)
- 复用方式：直接迁移思路 + Python 改写（不原样拷贝）
- 目标落位（guiagent_v2）：`guiagent_v2/runtime`（step 级决策辅助）
- 依赖：`hashlib`、当前 event bus、steps context
- 风险：阈值配置不当导致误判
- 验收标准：
  - 连续重复动作可触发 `loop_warning` 事件
  - 页面停滞达到阈值后触发 `handover` 建议

## P0-2 上下文压缩器

- 来源模块：`demo/browser-use/browser_use/agent/message_manager/service.py`
- 复用方式：直接迁移机制（窗口 + 压缩触发策略）
- 目标落位（guiagent_v2）：`guiagent_v2/runtime`（history compaction service）
- 依赖：LLM 压缩调用、runtime 上下文对象
- 风险：压缩摘要失真
- 验收标准：
  - 长任务下 prompt 长度可控
  - 压缩后任务成功率不显著下降

## P0-3 会话化任务服务

- 来源模块：`demo/browser-use/browser_use/skill_cli/server.py`
- 复用方式：适配改写（保留 Python，采用 server/session 模式）
- 目标落位（guiagent_v2）：`guiagent_v2/runtime/task_service.py` 的下一阶段
- 依赖：IPC（socket）、session registry、状态 API
- 风险：多进程管理复杂
- 验收标准：
  - 支持同 run 下多 task 会话隔离
  - 支持 server 重启后的任务状态恢复策略

## P0-4 执行前策略门禁

- 来源模块：`demo/agent-browser/src/action-policy.ts`
- 复用方式：Python 重写策略引擎（allow/deny/confirm）
- 目标落位（guiagent_v2）：`guiagent_v2/runtime`（pre-assertion 前置门禁）
- 依赖：intent/action 分类映射、运行时配置加载
- 风险：分类体系不一致
- 验收标准：
  - 每个 action 在执行前有明确门禁决策
  - 支持策略文件热加载

## P0-5 后验 Diff 校验

- 来源模块：`demo/agent-browser/src/diff.ts`
- 复用方式：策略复用 + Python 版本实现
- 目标落位（guiagent_v2）：`guiagent_v2/action_engine/post_check.py`
- 依赖：截图、快照文本、阈值配置
- 风险：动态页面误报
- 验收标准：
  - 输出 `changed/mismatch_percentage` 指标
  - 可作为 post_check 失败证据

## P0-6 AgentBrowserSkill（Web 旁路 Skill）

- 来源模块：`demo/agent-browser/src/daemon.ts`, `demo/agent-browser/src/protocol.ts`, `demo/agent-browser/cli/src/main.rs`
- 复用方式：外部进程集成（Skill wrapper）+ Python 适配
- 目标落位（guiagent_v2）：`guiagent_v2` 的 skill 旁路层（建议由 runtime 路由器调用）
- 依赖：本地 agent-browser binary、IPC 命令通道、session 管理
- 风险：跨语言调试成本、Web/移动上下文切换失败
- 验收标准：
  - 可通过 skill 调用完成 Web 子任务（打开页面、查找、点击、提取）
  - skill 失败后能自动 fallback 到 `mobile_native`
  - 不影响原有移动端原子动作成功率

## P1 清单

## P1-1 动作注册中心（ActionRegistry）

- 来源模块：`demo/browser-use/browser_use/tools/registry/service.py`
- 复用方式：适配改写（装饰器 + 参数模型）
- 目标落位（guiagent_v2）：`guiagent_v2/action_engine`
- 依赖：Pydantic/dataclass 模型体系
- 风险：与 legacy action 映射冲突
- 验收标准：
  - 新动作可通过注册接入，不改主分发逻辑
  - 参数校验失败能给出结构化错误

## P1-2 Typed Event 扩展

- 来源模块：`demo/browser-use/browser_use/browser/events.py`
- 复用方式：字段策略借鉴 + 轻量类型化
- 目标落位（guiagent_v2）：`guiagent_v2/runtime/event_bus.py`
- 依赖：事件模型定义文件、metrics 统计器
- 风险：事件版本兼容
- 验收标准：
  - 关键事件有固定字段集合和默认 timeout
  - 事件 schema 变更可版本化

## P1-3 Watchdog 插件骨架

- 来源模块：`demo/browser-use/browser_use/browser/watchdog_base.py`
- 复用方式：结构借鉴 + 简化实现
- 目标落位（guiagent_v2）：`guiagent_v2/runtime/watchdogs/`
- 依赖：事件分发、session 状态对象
- 风险：并发复杂度上升
- 验收标准：
  - 至少实现 `crash`、`security` 两类 watchdog
  - watchdog 异常不阻塞主执行链

## P1-4 Domain Filter 能力

- 来源模块：`demo/agent-browser/src/domain-filter.ts`
- 复用方式：外部进程集成优先（agent-browser adapter）
- 目标落位（guiagent_v2）：`WebAutomationAdapter` 安全配置层
- 依赖：浏览器自动化后端（Playwright/CDP）
- 风险：白名单维护成本
- 验收标准：
  - 非白名单域名请求可被稳定阻断
  - 阻断事件可记录到 `events.jsonl`

## P1-5 WebSkillRouter（移动/网页路由）

- 来源模块：`demo/browser-use/browser_use/skill_cli/server.py`（会话路由思路）+ `demo/agent-browser/src/action-policy.ts`（策略门禁）
- 复用方式：Python 重写路由层
- 目标落位（guiagent_v2）：`runtime` 调度层（action 前路由）
- 依赖：intent_key 分类、技能注册信息、运行时上下文
- 风险：路由规则过松导致误入 web_skill
- 验收标准：
  - `web:*` 类 intent 才允许进入 `web_skill`
  - 系统动作 intent 永不进入 `web_skill`
  - 路由决策事件可审计

## P2 清单

## P2-1 Snapshot Ref 全量体系

- 来源模块：`demo/agent-browser/src/snapshot.ts`
- 复用方式：外部进程调用为主，逐步内建
- 目标落位（guiagent_v2）：`state_engine + WebAutomationAdapter`
- 依赖：浏览器访问树、元素引用持久化
- 风险：动态页面 ref 抖动
- 验收标准：
  - 能输出 `ref -> selector/meta` 映射
  - 执行动作可按 ref 直达元素

## P2-2 Stream Server 接管通道

- 来源模块：`demo/agent-browser/src/stream-server.ts`
- 复用方式：外部进程集成
- 目标落位（guiagent_v2）：控制面（未来前端）
- 依赖：WebSocket、鉴权、事件桥接
- 风险：输入注入安全风险
- 验收标准：
  - 只允许本地/鉴权来源注入
  - 输入注入行为可审计可回放

## P2-3 browser-use Agent 主循环整段迁移

- 来源模块：`demo/browser-use/browser_use/agent/service.py`
- 复用方式：不建议整段迁移，建议按机制拆取
- 目标落位（guiagent_v2）：中长期架构演进参考
- 依赖：全套工具与事件生态
- 风险：高耦合、高改造成本
- 验收标准：
  - 若执行该项，必须先完成 P0/P1 并有稳定接口层

## 统一建议

1. 先做 P0：以低风险快速增强当前 `guiagent_v2`。
2. P1 作为结构升级：强化动作扩展与运行时治理。
3. P2 仅在控制面与 Web 自动化主线成熟后推进。

## 推荐推进节奏（移动端优先）

1. 第 1 批：`P0-1/P0-2/P0-4`（循环检测、上下文压缩、策略门禁）。
2. 第 2 批：`P0-3 + P1-5`（会话化任务服务 + 路由器）。
3. 第 3 批：`P0-6 + P1-4`（AgentBrowserSkill + DomainFilter）。
4. 第 4 批：其余 P1 与 P2（watchdog、snapshot ref、stream 接管）。

## 与接口草案映射

- `WebAutomationAdapter`：承接 P1-4、P2-1、P2-2
- `ActionRegistry`：承接 P1-1
- `GuardPolicy`：承接 P0-4
- `SessionRuntime`：承接 P0-3、P1-2、P1-3
- `AgentBrowserSkill`：承接 P0-6
- `WebSkillRouter`：承接 P1-5
