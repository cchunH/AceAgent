-- ============================================================
-- Uni-Mind 层次化智能体决策系统 - 参考数据库 Schema
-- 基于项目实际数据结构设计，适用于 MySQL 8.0+
-- ============================================================

-- -----------------------------------------------------------
-- 1. 会话与任务管理
-- -----------------------------------------------------------

CREATE TABLE sessions (
    session_id       VARCHAR(64)  PRIMARY KEY COMMENT '会话唯一标识 (sess-<uuid>)',
    created_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    task_count       INT          NOT NULL DEFAULT 0,
    last_request_id  VARCHAR(64)  NULL,
    metadata         JSON         NULL COMMENT '会话级扩展元数据'
) COMMENT='运行时会话';

CREATE TABLE tasks (
    task_id          VARCHAR(64)  PRIMARY KEY COMMENT '时间戳+uuid',
    request_id       VARCHAR(64)  NOT NULL UNIQUE,
    session_id       VARCHAR(64)  NULL,
    run_name         VARCHAR(128) NOT NULL COMMENT '运行组名称',
    run_id           VARCHAR(192) NOT NULL COMMENT 'run_name:task_id',
    instruction      TEXT         NOT NULL COMMENT '用户任务指令',
    runtime_mode     VARCHAR(32)  NOT NULL DEFAULT 'legacy' COMMENT 'legacy|guiagent_v2_shadow|guiagent_v2',
    status           VARCHAR(16)  NOT NULL DEFAULT 'QUEUED' COMMENT 'QUEUED|RUNNING|SUCCESS|FAILED|HANDOVER',
    submitted_at     DATETIME(3)  NOT NULL,
    started_at       DATETIME(3)  NULL,
    completed_at     DATETIME(3)  NULL,
    result           JSON         NULL COMMENT '执行结果',
    error            TEXT         NULL,
    INDEX idx_session (session_id),
    INDEX idx_status  (status),
    INDEX idx_run     (run_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
) COMMENT='任务记录';

-- -----------------------------------------------------------
-- 2. 意图契约层
-- -----------------------------------------------------------

CREATE TABLE intent_metadata (
    intent_key       VARCHAR(128) PRIMARY KEY COMMENT '格式: domain:verb:object',
    description      VARCHAR(512) NOT NULL,
    risk_level       VARCHAR(16)  NOT NULL DEFAULT 'LOW' COMMENT 'LOW|MEDIUM|HIGH|CRITICAL',
    aliases          JSON         NOT NULL COMMENT '别名列表 ["alias1","alias2"]',
    pre_conditions   JSON         NOT NULL COMMENT '前置条件列表',
    post_expectations JSON        NOT NULL COMMENT '期望后置状态列表',
    created_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)
) COMMENT='意图元数据契约';

-- -----------------------------------------------------------
-- 3. 蓝图与锚点
-- -----------------------------------------------------------

CREATE TABLE blueprints (
    id               BIGINT       AUTO_INCREMENT PRIMARY KEY,
    intent_key       VARCHAR(128) NOT NULL,
    app_state        VARCHAR(128) NOT NULL DEFAULT 'global:DEFAULT',
    version          VARCHAR(32)  NOT NULL DEFAULT 'v0.1.0',
    ref_screen_width  INT         NOT NULL DEFAULT 1080,
    ref_screen_height INT         NOT NULL DEFAULT 2340,
    post_expectations JSON        NOT NULL COMMENT '执行后期望文本列表',
    metadata         JSON         NULL,
    created_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    UNIQUE KEY uk_intent_state_ver (intent_key, app_state, version),
    INDEX idx_intent (intent_key),
    FOREIGN KEY (intent_key) REFERENCES intent_metadata(intent_key)
) COMMENT='技能蓝图（高精地图）';

CREATE TABLE anchor_nodes (
    id               BIGINT       AUTO_INCREMENT PRIMARY KEY,
    blueprint_id     BIGINT       NOT NULL,
    anchor_id        VARCHAR(16)  NOT NULL COMMENT '如 a0, a1',
    type             VARCHAR(8)   NOT NULL COMMENT 'TEXT|ICON',
    text             VARCHAR(256) NOT NULL COMMENT '可见文本或图标描述',
    norm_x           FLOAT        NOT NULL COMMENT '归一化 x',
    norm_y           FLOAT        NOT NULL COMMENT '归一化 y',
    norm_w           FLOAT        NOT NULL COMMENT '归一化宽度',
    norm_h           FLOAT        NOT NULL COMMENT '归一化高度',
    role             VARCHAR(12)  NOT NULL COMMENT 'CORE|AUXILIARY',
    stability_score  FLOAT        NOT NULL DEFAULT 1.0 COMMENT '稳定性 0.0-1.0',
    zone             VARCHAR(8)   NOT NULL COMMENT 'top|middle|bottom',
    UNIQUE KEY uk_bp_anchor (blueprint_id, anchor_id),
    FOREIGN KEY (blueprint_id) REFERENCES blueprints(id) ON DELETE CASCADE
) COMMENT='蓝图锚点节点';

CREATE TABLE blueprint_patches (
    patch_id         VARCHAR(64)  PRIMARY KEY COMMENT 'uuid',
    target_intent_key VARCHAR(128) NOT NULL,
    target_state     VARCHAR(128) NOT NULL,
    version          VARCHAR(32)  NOT NULL,
    delta            JSON         NOT NULL COMMENT '变更内容',
    rollback_to      VARCHAR(32)  NULL COMMENT '回滚目标版本',
    applied_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_target (target_intent_key, target_state),
    FOREIGN KEY (target_intent_key) REFERENCES intent_metadata(intent_key)
) COMMENT='蓝图热补丁';

-- -----------------------------------------------------------
-- 4. 静态骨架（离线进化产物）
-- -----------------------------------------------------------

CREATE TABLE static_skeletons (
    id               BIGINT       AUTO_INCREMENT PRIMARY KEY,
    intent_key       VARCHAR(128) NOT NULL,
    app_state        VARCHAR(128) NOT NULL DEFAULT 'global:DEFAULT',
    signature        VARCHAR(64)  NOT NULL COMMENT '骨架哈希签名',
    stable_ratio     FLOAT        NOT NULL COMMENT '稳定元素占比',
    frame_count      INT          NOT NULL COMMENT '分析帧数',
    sample_count     INT          NOT NULL COMMENT '采样数',
    nodes            JSON         NOT NULL COMMENT '稳定 UI 节点列表',
    dynamic_slots    JSON         NULL COMMENT '动态变化区域',
    created_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_intent_state (intent_key, app_state)
) COMMENT='幽灵骨架（多帧交集去噪产物）';

-- -----------------------------------------------------------
-- 5. 执行请求与结果
-- -----------------------------------------------------------

CREATE TABLE execution_requests (
    request_id       VARCHAR(64)  PRIMARY KEY,
    task_id          VARCHAR(64)  NOT NULL,
    step_id          INT          NOT NULL,
    intent_key       VARCHAR(128) NOT NULL,
    action_name      VARCHAR(32)  NOT NULL,
    action_arguments JSON         NOT NULL,
    expected_semantics JSON       NULL COMMENT '断言期望文本',
    check_region     JSON         NULL COMMENT '检查区域',
    fail_policy      VARCHAR(32)  NOT NULL DEFAULT 'HANDOVER_S2',
    timeout_ms       INT          NOT NULL DEFAULT 3000,
    retry_max        INT          NOT NULL DEFAULT 1,
    retry_backoff_ms INT          NOT NULL DEFAULT 500,
    created_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_task_step (task_id, step_id),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id),
    FOREIGN KEY (intent_key) REFERENCES intent_metadata(intent_key)
) COMMENT='执行请求';

CREATE TABLE execution_results (
    id               BIGINT       AUTO_INCREMENT PRIMARY KEY,
    request_id       VARCHAR(64)  NOT NULL,
    status           VARCHAR(16)  NOT NULL COMMENT 'SUCCESS|FAILED|HANDOVER',
    assertion_passed BOOLEAN      NOT NULL DEFAULT FALSE,
    assertion_reason VARCHAR(64)  NULL,
    post_check_passed BOOLEAN     NULL,
    post_check_reason VARCHAR(64) NULL,
    recovery_level   VARCHAR(8)   NOT NULL DEFAULT 'NONE' COMMENT 'NONE|L1|L2|L3',
    latency_ms       INT          NOT NULL DEFAULT 0,
    created_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_request (request_id),
    FOREIGN KEY (request_id) REFERENCES execution_requests(request_id)
) COMMENT='执行结果';

-- -----------------------------------------------------------
-- 6. 事件流（结构化审计日志）
-- -----------------------------------------------------------

CREATE TABLE events (
    id               BIGINT       AUTO_INCREMENT PRIMARY KEY,
    ts               DATETIME(3)  NOT NULL,
    run_id           VARCHAR(192) NOT NULL,
    task_id          VARCHAR(64)  NOT NULL,
    session_id       VARCHAR(64)  NULL,
    step_id          INT          NOT NULL DEFAULT 0,
    chain_mode       VARCHAR(32)  NULL,
    event_type       VARCHAR(48)  NOT NULL COMMENT 'guard_decision|skill_route|skill_fallback|watchdog_alert|...',
    status           VARCHAR(16)  NOT NULL,
    intent_key       VARCHAR(128) NULL,
    event_schema_version VARCHAR(8) NOT NULL DEFAULT 'v1',
    extra            JSON         NULL COMMENT '事件类型特有字段',
    INDEX idx_task    (task_id, step_id),
    INDEX idx_run     (run_id),
    INDEX idx_type    (event_type),
    INDEX idx_ts      (ts),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
) COMMENT='结构化事件流（events.jsonl 持久化）';

-- -----------------------------------------------------------
-- 7. 人工确认记录
-- -----------------------------------------------------------

CREATE TABLE confirmations (
    confirm_id       VARCHAR(192) PRIMARY KEY COMMENT 'run_id:task_id:step_id',
    run_id           VARCHAR(192) NOT NULL,
    task_id          VARCHAR(64)  NOT NULL,
    step_id          INT          NOT NULL,
    session_id       VARCHAR(64)  NULL,
    intent_key       VARCHAR(128) NULL,
    channel          VARCHAR(32)  NULL COMMENT '执行通道',
    route_reason     VARCHAR(128) NULL,
    policy_decision  VARCHAR(16)  NOT NULL DEFAULT 'confirm',
    policy_reason    VARCHAR(128) NULL,
    policy_category  VARCHAR(32)  NULL,
    status           VARCHAR(16)  NOT NULL DEFAULT 'PENDING' COMMENT 'PENDING|APPROVED|REJECTED',
    decision         VARCHAR(16)  NULL COMMENT 'approve|reject',
    actor            VARCHAR(64)  NULL COMMENT '决策者',
    source           VARCHAR(64)  NULL COMMENT '决策来源',
    note             TEXT         NULL,
    created_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    resolved_at      DATETIME(3)  NULL,
    INDEX idx_status  (status),
    INDEX idx_task    (task_id),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
) COMMENT='人工确认审批记录';

-- -----------------------------------------------------------
-- 8. 策略治理
-- -----------------------------------------------------------

CREATE TABLE guard_policies (
    id               BIGINT       AUTO_INCREMENT PRIMARY KEY,
    policy_source    VARCHAR(128) NOT NULL COMMENT '策略文件来源',
    policy_version   VARCHAR(32)  NOT NULL,
    intent_pattern   VARCHAR(128) NULL COMMENT '匹配的意图模式',
    domain           VARCHAR(64)  NULL COMMENT '策略域',
    category         VARCHAR(32)  NOT NULL COMMENT 'baseline|risk_control|policy_rules|route_guard',
    decision         VARCHAR(16)  NOT NULL COMMENT 'allow|deny|confirm',
    reason           VARCHAR(128) NOT NULL,
    priority         INT          NOT NULL DEFAULT 0,
    enabled          BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_intent  (intent_pattern),
    INDEX idx_domain  (domain)
) COMMENT='守卫策略规则';

-- -----------------------------------------------------------
-- 9. Agent 状态池（InfoPool 快照）
-- -----------------------------------------------------------

CREATE TABLE info_pool_snapshots (
    id               BIGINT       AUTO_INCREMENT PRIMARY KEY,
    task_id          VARCHAR(64)  NOT NULL,
    step_id          INT          NOT NULL,
    instruction      TEXT         NOT NULL,
    plan             TEXT         NULL,
    current_subgoal  VARCHAR(512) NULL,
    progress_status  VARCHAR(256) NULL,
    important_notes  TEXT         NULL,
    last_action      VARCHAR(256) NULL,
    last_summary     VARCHAR(512) NULL,
    last_action_thought TEXT      NULL,
    error_flag_plan  BOOLEAN      NOT NULL DEFAULT FALSE,
    screen_width     INT          NOT NULL DEFAULT 1080,
    screen_height    INT          NOT NULL DEFAULT 2340,
    keyboard_pre     BOOLEAN      NOT NULL DEFAULT FALSE,
    keyboard_post    BOOLEAN      NOT NULL DEFAULT FALSE,
    perception_pre   JSON         NULL COMMENT '动作前感知元素列表',
    perception_post  JSON         NULL COMMENT '动作后感知元素列表',
    action_history   JSON         NULL COMMENT '动作历史',
    summary_history  JSON         NULL COMMENT '摘要历史',
    action_outcomes  JSON         NULL COMMENT '结果编码列表 (A/B/C)',
    captured_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_task_step (task_id, step_id),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
) COMMENT='Agent 状态池快照（用于回放与审计）';

-- -----------------------------------------------------------
-- 10. 技能库
-- -----------------------------------------------------------

CREATE TABLE skills (
    id               BIGINT       AUTO_INCREMENT PRIMARY KEY,
    name             VARCHAR(128) NOT NULL UNIQUE,
    description      TEXT         NOT NULL,
    precondition     VARCHAR(512) NULL COMMENT '使用前置条件',
    arguments        JSON         NOT NULL COMMENT '参数名列表',
    action_sequence  JSON         NOT NULL COMMENT '原子动作序列 [{name, arguments_map}]',
    source           VARCHAR(32)  NOT NULL DEFAULT 'learned' COMMENT 'builtin|learned|imported',
    created_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)
) COMMENT='技能库（经验学习产物）';

-- -----------------------------------------------------------
-- 11. 拓扑匹配日志
-- -----------------------------------------------------------

CREATE TABLE topology_match_logs (
    id               BIGINT       AUTO_INCREMENT PRIMARY KEY,
    task_id          VARCHAR(64)  NOT NULL,
    step_id          INT          NOT NULL,
    blueprint_id     BIGINT       NULL,
    matched          INT          NOT NULL,
    total_expected   INT          NOT NULL,
    confidence       FLOAT        NOT NULL,
    core_confidence  FLOAT        NOT NULL DEFAULT 0.0,
    aux_confidence   FLOAT        NOT NULL DEFAULT 0.0,
    geometry_confidence FLOAT     NOT NULL DEFAULT 0.0,
    matched_core     INT          NOT NULL DEFAULT 0,
    matched_aux      INT          NOT NULL DEFAULT 0,
    total_core       INT          NOT NULL DEFAULT 0,
    total_aux        INT          NOT NULL DEFAULT 0,
    transform_mode   VARCHAR(16)  NOT NULL DEFAULT 'identity' COMMENT 'identity|scale|affine_norm',
    transform_fit_error FLOAT     NOT NULL DEFAULT 0.0,
    reason_code      VARCHAR(64)  NOT NULL,
    matched_anchor_ids JSON       NULL,
    created_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_task_step (task_id, step_id),
    INDEX idx_blueprint (blueprint_id),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id),
    FOREIGN KEY (blueprint_id) REFERENCES blueprints(id)
) COMMENT='拓扑匹配结果日志';

-- -----------------------------------------------------------
-- 12. 循环检测观测
-- -----------------------------------------------------------

CREATE TABLE loop_observations (
    id               BIGINT       AUTO_INCREMENT PRIMARY KEY,
    task_id          VARCHAR(64)  NOT NULL,
    step_id          INT          NOT NULL,
    action_signature VARCHAR(64)  NOT NULL COMMENT 'SHA1 of action',
    page_fingerprint VARCHAR(64)  NOT NULL COMMENT 'SHA1 of page state',
    repeated_action_count INT     NOT NULL DEFAULT 0,
    stagnation_steps INT          NOT NULL DEFAULT 0,
    loop_score       FLOAT        NOT NULL DEFAULT 0.0 COMMENT '0.0-1.0',
    should_warn      BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at       DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_task    (task_id, step_id),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
) COMMENT='循环检测观测记录';

-- -----------------------------------------------------------
-- 13. 状态机转换日志
-- -----------------------------------------------------------

CREATE TABLE state_transitions (
    id               BIGINT       AUTO_INCREMENT PRIMARY KEY,
    task_id          VARCHAR(64)  NOT NULL,
    step_id          INT          NOT NULL,
    prev_state       VARCHAR(24)  NOT NULL COMMENT 'INIT|ROUTED|GUARDED|CONFIRM_PENDING|EXECUTING_WEB|EXECUTING_MOBILE|FALLBACK|VERIFYING|HANDOVER|COMPLETED',
    next_state       VARCHAR(24)  NOT NULL,
    reason           VARCHAR(128) NOT NULL,
    ok               BOOLEAN      NOT NULL DEFAULT TRUE,
    transitioned_at  DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_task_step (task_id, step_id),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
) COMMENT='执行器状态机转换日志';
