# 风险点与优化建议

## P0（应优先处理）

1. 密钥安全风险  
   `config.py` 中 `SILICONFLOW_API_KEY` 存在硬编码默认值。应改为仅从环境变量读取，并在缺失时明确报错。

2. 双轨功能不可通过参数启用  
   `USE_DUAL_TRACK` 在 `orchestrator.py` 里是硬编码 `False`。建议增加 CLI 参数（如 `--use_dual_track`）并写入日志，避免功能“存在但不可用”。

3. 运行时人工阻塞  
   多任务模式每个任务后 `input("Press Enter...")`，不适合无人值守批量运行。建议增加 `--non_interactive` 参数控制。

## P1（稳定性优化）

1. QuickVerifier 解析兜底缺陷  
   `PlannerExecutor.parse_response` 失败兜底里使用 `InfoPool.plan`（类属性语义不正确），应改为实例上下文回退。

2. 异步笔记线程生命周期不受控  
   异步 Notetaker 未统一 join，任务结束时可能仍在写共享状态。建议线程池化并在任务收尾显式等待或取消。

3. API 调用耗时日志有异常缩放  
   `get_model_api_response` 中 `elapsed_time = elapsed_time * 0.6` 会导致监控数据失真，应移除。

4. 重复导入与历史注释较多  
   `orchestrator.py` 存在重复 import 和大段注释遗留，建议清理降低维护成本。

## P2（工程化增强）

1. 抽象状态机  
   可将 `run_single_task` 的 while 循环拆成显式状态机（Perceive/Plan/Act/Verify/Learn），提升可测试性与可替换性。

2. 统一协议对象  
   当前 Prompt/Response 解析依赖字符串分段，建议引入结构化 schema（Pydantic/JSON schema）减少解析脆弱性。

3. 指标体系  
   建议沉淀统一指标：成功率、平均步数、平均验证耗时、JSON 修复命中率、任务中断原因分布。

4. 测试覆盖  
   当前以脚本调试为主。建议补齐：
   - 动作 JSON 修复单测
   - VerifyCore 结果映射测试
   - 持久化知识读写测试
   - 快轨回退专家轨的集成测试

## 快速落地顺序建议

1. 先做密钥治理 + 非交互运行 + 双轨参数化（风险收益比最高）  
2. 再做线程收尾与耗时日志修正  
3. 最后推进状态机重构与结构化 schema

