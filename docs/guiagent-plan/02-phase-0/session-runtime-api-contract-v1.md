# SessionRuntime API Contract v1

## 文档元信息

- 状态：`active`
- 版本：`v1.2`
- 更新时间：`2026-03-08`
- 适用范围：`guiagent_v2/runtime/session_runtime_server.py`

## 1. 服务说明

1. 协议：HTTP/1.1（本地回环地址）
2. 数据格式：`application/json; charset=utf-8`
3. 默认地址：`http://127.0.0.1:8787`
4. 统一响应结构：
- 成功：`{"ok": true, "data": ...}`
- 失败：`{"ok": false, "error": {"code": "...", "message": "..."}}`
5. 响应头：
- `X-Session-Runtime-Instance-Id`: 当前服务实例 ID（用于排障和实例定位）。

## 2. 鉴权

1. 鉴权开关：
- 启动时配置 `api_token` 则开启鉴权。

2. 鉴权范围：
- 默认仅写接口需要 token（POST/DELETE）。
- 若启用 `require_auth_on_read=true`，读接口也需要 token。

3. Token 传递方式（任选其一）：
- Header: `X-API-Token: <token>`
- Header: `Authorization: Bearer <token>`

4. 未授权响应：
- `401 UNAUTHORIZED`
- `{"ok": false, "error": {"code": "UNAUTHORIZED", "message": "missing or invalid api token"}}`

## 2.1 控制面审计上下文（写接口可选）

写接口（`POST/DELETE`）支持以下可选请求头，供审计事件记录：
- `X-Actor`: 操作者标识（如 `frontend-user-1`）。
- `X-Source`: 请求来源（如 `web-console` / `scheduler`）。
- `X-Trace-Id` 或 `X-Request-Id`: 链路追踪 ID。

## 3. 接口列表

### 3.1 健康检查

- `GET /health`
- 说明：服务健康状态，不受读鉴权影响。
- 响应：`{"ok": true, "data": {"status": "ok", "instance_id": "...", "pid": 12345}}`

### 3.2 会话接口

1. `GET /sessions`
- 说明：列出会话。

2. `GET /sessions/{session_id}`
- 说明：查询单会话。

3. `POST /sessions`
- 说明：创建或确保会话。
- 请求体：
```json
{
  "session_id": "sess-xxx",
  "metadata": {"source": "frontend"}
}
```

4. `DELETE /sessions/{session_id}`
- 说明：关闭并移除会话。

### 3.3 任务接口

1. `GET /tasks?session_id=&status=`
- 说明：按会话和状态查询任务。

2. `GET /tasks/{request_id}`
- 说明：查询单任务。

3. `POST /tasks`
- 说明：提交任务。
- 请求体：
```json
{
  "instruction": "open app",
  "session_id": "sess-xxx",
  "runtime_mode": "guiagent_v2",
  "run_name": "api",
  "task_id": null,
  "run_options": {}
}
```

4. `POST /tasks/{request_id}/wait`
- 说明：等待任务结束或超时。
- 请求体：
```json
{
  "timeout": 1.0
}
```

### 3.4 运行时状态接口

1. `GET /runtime/status?run_id=&status=&session_id=`
- 说明：查询运行时状态列表。

2. `GET /runtime/status/{run_id}/{task_id}`
- 说明：查询单任务运行时状态。

3. `GET /runtime/timeline/{run_id}/{task_id}`
- 说明：查询事件时间线。
- 说明补充：对 `POST /tasks`、`POST /tasks/{request_id}/wait` 等任务相关写操作，会产生 `control_plane_audit` 事件并按对应 `run_id/task_id` 进入同一时间线。

## 4. 错误码

1. `INVALID_BODY`
2. `INVALID_INSTRUCTION`
3. `INVALID_PATH`
4. `TASK_NOT_FOUND`
5. `SESSION_NOT_FOUND`
6. `RUNTIME_STATUS_NOT_FOUND`
7. `TASK_SUBMIT_FAILED`
8. `UNAUTHORIZED`
9. `NOT_FOUND`

## 5. 兼容约束

1. v1 阶段保证：
- 现有路径与字段名稳定。
- 错误码名称稳定。
- 允许在 `data` 中新增非破坏字段（如 `instance_id/pid`）。

2. v2 预留：
- 增加分页参数（tasks/status）。
- 增加批量查询接口。
- 增加请求追踪字段（`trace_id`）。
- 增加审计查询接口（`/runtime/audit`）。

## 6. 运行治理参数（Server 启动）

`run.py --start_session_runtime_server` 相关新增参数：
- `--session_runtime_lockfile_path`：多实例锁文件路径（空则按默认规则生成）。
- `--session_runtime_allow_port_fallback`：端口冲突时允许回退到系统分配端口。
- `--session_runtime_audit_log_path`：控制面写操作审计 JSONL 路径。
