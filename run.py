from orchestrator import run_single_task
from orchestrator import (
    Perceptor,
    DEFAULT_PERCEPTION_ARGS,
    ADB_PATH,
    INIT_HEURISTICS,
    INIT_SKILLS,
    DEFAULT_MODEL,
)
from guiagent_v2.runtime.orchestrator_v2 import run_single_task_with_runtime
from guiagent_v2.runtime.session_runtime_server import (
    start_global_session_runtime_server,
    stop_global_session_runtime_server,
)

import torch
import os
import json
import shutil
import time


def _run_with_mode(runtime_mode: str, **kwargs):
    if runtime_mode == "legacy":
        kwargs.pop("v2_skip_legacy", None)
        kwargs.pop("guard_policy_path", None)
        kwargs.pop("guard_policy_reload_interval", None)
        kwargs.pop("watchdog_policy_path", None)
        kwargs.pop("watchdog_policy_reload_interval", None)
        kwargs.pop("session_id", None)
        kwargs.pop("strict_event_schema", None)
        kwargs.pop("status_timeline_max_events", None)
        kwargs.pop("web_max_steps", None)
        kwargs.pop("web_replan_max_attempts", None)
        kwargs.pop("confirm_wait_timeout", None)
        kwargs.pop("confirm_poll_interval", None)
        kwargs.pop("mobile_execution_mode", None)
        kwargs.pop("mobile_wait_ms", None)
        kwargs.pop("v2_max_steps", None)
        kwargs.pop("v2_use_live_perception", None)
        kwargs.pop("blueprint_vector_backend", None)
        kwargs.pop("blueprint_vector_plugin", None)
        kwargs.pop("blueprint_embedding_dim", None)
        return run_single_task(**kwargs)
    kwargs["runtime_mode"] = runtime_mode
    return run_single_task_with_runtime(**kwargs)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--instruction", type=str, default=None)
    parser.add_argument("--max_itr", type=int, default=40)
    parser.add_argument("--max_consecutive_failures", type=int, default=5)
    parser.add_argument("--max_repetitive_actions", type=int, default=5)
    parser.add_argument("--overwrite_task_log_dir", action="store_true", default=False)
    parser.add_argument("--enable_experience_retriever", action="store_true", default=False)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--log_root", type=str, default=None)
    parser.add_argument("--run_name", type=str, default="test")
    parser.add_argument("--tasks_json", type=str, default=None)
    parser.add_argument("--specified_heuristics_path", type=str, default=None)
    parser.add_argument("--specified_skills_path", type=str, default=None)
    parser.add_argument("--screenrecord", action="store_true", default=False)
    parser.add_argument("--setting", type=str, default="evolution", choices=["individual", "evolution"])
    parser.add_argument(
        "--runtime_mode",
        type=str,
        default="legacy",
        choices=["legacy", "guiagent_v2_shadow", "guiagent_v2"],
    )
    parser.add_argument(
        "--v2_skip_legacy",
        action="store_true",
        default=False,
        help="Only for runtime_mode=guiagent_v2: skip delegating to legacy orchestrator.",
    )
    parser.add_argument(
        "--guard_policy_path",
        type=str,
        default=None,
        help="Optional JSON path for guiagent_v2 guard policy.",
    )
    parser.add_argument(
        "--guard_policy_reload_interval",
        type=float,
        default=1.0,
        help="Reload interval (seconds) for guard policy file checks.",
    )
    parser.add_argument(
        "--session_id",
        type=str,
        default=None,
        help="Optional logical session id for guiagent_v2 task tracking.",
    )
    parser.add_argument(
        "--strict_event_schema",
        action="store_true",
        default=False,
        help="Fail-fast when guiagent_v2 runtime emits schema-invalid events.",
    )
    parser.add_argument(
        "--status_timeline_max_events",
        type=int,
        default=None,
        help="Optional cap for in-memory timeline events per task in guiagent_v2 status store.",
    )
    parser.add_argument(
        "--web_max_steps",
        type=int,
        default=3,
        help="Max web steps for guiagent_v2 web skill execution plan.",
    )
    parser.add_argument(
        "--web_replan_max_attempts",
        type=int,
        default=1,
        help="Max local replan attempts for guiagent_v2 web execution.",
    )
    parser.add_argument(
        "--confirm_wait_timeout",
        type=float,
        default=0.0,
        help="Seconds to wait for guard confirm decision before handover in guiagent_v2.",
    )
    parser.add_argument(
        "--confirm_poll_interval",
        type=float,
        default=0.5,
        help="Polling interval in seconds for guard confirm decision checks.",
    )
    parser.add_argument(
        "--mobile_execution_mode",
        type=str,
        default="auto",
        choices=["auto", "shadow", "device"],
        help="Mobile-native execution mode for guiagent_v2: auto (fallback), shadow, or device.",
    )
    parser.add_argument(
        "--mobile_wait_ms",
        type=int,
        default=1000,
        help="Default wait duration for mobile Wait action in guiagent_v2.",
    )
    parser.add_argument(
        "--v2_max_steps",
        type=int,
        default=4,
        help="Max task steps for guiagent_v2 when --v2_skip_legacy is enabled.",
    )
    parser.add_argument(
        "--v2_use_live_perception",
        action="store_true",
        default=False,
        help="Enable live Perceptor snapshots for guiagent_v2 pre/post step context.",
    )
    parser.add_argument(
        "--blueprint_vector_backend",
        type=str,
        default=None,
        help="Blueprint vector backend: memory|custom (default from env GUIAGENT_BLUEPRINT_VECTOR_BACKEND).",
    )
    parser.add_argument(
        "--blueprint_vector_plugin",
        type=str,
        default=None,
        help="Custom blueprint vector plugin spec '<module>:<factory>' when backend=custom.",
    )
    parser.add_argument(
        "--blueprint_embedding_dim",
        type=int,
        default=None,
        help="Embedding dimension for blueprint vector retrieval (default from env GUIAGENT_BLUEPRINT_EMBEDDING_DIM).",
    )
    parser.add_argument(
        "--watchdog_policy_path",
        type=str,
        default=None,
        help="Optional JSON path for guiagent_v2 watchdog policy.",
    )
    parser.add_argument(
        "--watchdog_policy_reload_interval",
        type=float,
        default=1.0,
        help="Reload interval (seconds) for watchdog policy file checks.",
    )
    parser.add_argument(
        "--start_session_runtime_server",
        action="store_true",
        default=False,
        help="Start SessionRuntime HTTP API server and block.",
    )
    parser.add_argument(
        "--session_runtime_server_host",
        type=str,
        default="127.0.0.1",
        help="SessionRuntime HTTP API server bind host.",
    )
    parser.add_argument(
        "--session_runtime_server_port",
        type=int,
        default=8787,
        help="SessionRuntime HTTP API server bind port.",
    )
    parser.add_argument(
        "--session_runtime_state_path",
        type=str,
        default=None,
        help="Optional state file path for SessionRuntime server persistence.",
    )
    parser.add_argument(
        "--session_runtime_api_token",
        type=str,
        default=None,
        help="Optional API token for SessionRuntime server auth.",
    )
    parser.add_argument(
        "--session_runtime_auth_read",
        action="store_true",
        default=False,
        help="Require API token on read endpoints for SessionRuntime server.",
    )
    parser.add_argument(
        "--session_runtime_lockfile_path",
        type=str,
        default=None,
        help="Optional lockfile path for SessionRuntime multi-instance governance.",
    )
    parser.add_argument(
        "--session_runtime_allow_port_fallback",
        action="store_true",
        default=False,
        help="Allow SessionRuntime server to fall back to an ephemeral port on conflict.",
    )
    parser.add_argument(
        "--session_runtime_audit_log_path",
        type=str,
        default=None,
        help="Optional JSONL audit file path for SessionRuntime control-plane writes.",
    )

    args = parser.parse_args()
    torch.manual_seed(args.seed)

    if args.log_root is None:
        args.log_root = f"logs/{DEFAULT_MODEL}/unimind_agent"

    if args.start_session_runtime_server:
        session_state_path = args.session_runtime_state_path
        if session_state_path is None:
            session_state_path = os.path.join(
                args.log_root,
                "__runtime",
                "session_runtime_state.json",
            )
        session_audit_log_path = args.session_runtime_audit_log_path
        if session_audit_log_path is None:
            session_audit_log_path = os.path.join(
                args.log_root,
                "__runtime",
                "session_runtime_audit.jsonl",
            )
        host, port = start_global_session_runtime_server(
            host=args.session_runtime_server_host,
            port=args.session_runtime_server_port,
            persistence_path=session_state_path,
            api_token=args.session_runtime_api_token,
            require_auth_on_read=args.session_runtime_auth_read,
            lockfile_path=args.session_runtime_lockfile_path,
            allow_port_fallback=args.session_runtime_allow_port_fallback,
            audit_log_path=session_audit_log_path,
        )
        print(f"SessionRuntime API server started at http://{host}:{port}")
        print(f"SessionRuntime state path: {session_state_path}")
        print(f"SessionRuntime audit path: {session_audit_log_path}")
        if args.session_runtime_api_token:
            print("SessionRuntime API auth: enabled")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
        finally:
            stop_global_session_runtime_server()
        return

    if args.instruction is None and args.tasks_json is None:
        raise ValueError("You must provide either instruction or tasks_json.")
    if args.instruction is not None and args.tasks_json is not None:
        raise ValueError("You cannot provide both instruction and tasks_json.")

    default_perceptor_args = DEFAULT_PERCEPTION_ARGS

    if args.instruction is not None:
        if args.setting == "evolution":
            run_log_dir = f"{args.log_root}/{args.run_name}"
            os.makedirs(run_log_dir, exist_ok=True)
            persistent_heuristics_path = os.path.join(run_log_dir, "persistent_heuristics.txt")
            persistent_skills_path = os.path.join(run_log_dir, "persistent_skills.json")

            if not os.path.exists(persistent_heuristics_path):
                with open(persistent_heuristics_path, "w", encoding="utf-8") as f:
                    f.write(INIT_HEURISTICS)
            if not os.path.exists(persistent_skills_path):
                with open(persistent_skills_path, "w", encoding="utf-8") as f:
                    json.dump(INIT_SKILLS, f, indent=4)
        else:
            persistent_heuristics_path = None
            persistent_skills_path = None

        try:
            runtime_perceptor = None
            if args.v2_use_live_perception and args.runtime_mode in {"guiagent_v2_shadow", "guiagent_v2"}:
                runtime_perceptor = Perceptor(ADB_PATH, perception_args=default_perceptor_args)
            _run_with_mode(
                args.runtime_mode,
                instruction=args.instruction,
                run_name=args.run_name,
                log_root=args.log_root,
                heuristics_path=args.specified_heuristics_path,
                skills_path=args.specified_skills_path,
                persistent_heuristics_path=persistent_heuristics_path,
                persistent_skills_path=persistent_skills_path,
                perceptor=runtime_perceptor,
                perception_args=default_perceptor_args,
                max_itr=args.max_itr,
                max_consecutive_failures=args.max_consecutive_failures,
                max_repetitive_actions=args.max_repetitive_actions,
                overwrite_log_dir=args.overwrite_task_log_dir,
                err_to_planner_thresh=2,
                enable_experience_retriever=args.enable_experience_retriever,
                temperature=args.temperature,
                screenrecord=args.screenrecord,
                v2_skip_legacy=args.v2_skip_legacy,
                guard_policy_path=args.guard_policy_path,
                guard_policy_reload_interval=args.guard_policy_reload_interval,
                watchdog_policy_path=args.watchdog_policy_path,
                watchdog_policy_reload_interval=args.watchdog_policy_reload_interval,
                session_id=args.session_id,
                strict_event_schema=args.strict_event_schema,
                status_timeline_max_events=args.status_timeline_max_events,
                web_max_steps=args.web_max_steps,
                web_replan_max_attempts=args.web_replan_max_attempts,
                confirm_wait_timeout=args.confirm_wait_timeout,
                confirm_poll_interval=args.confirm_poll_interval,
                mobile_execution_mode=args.mobile_execution_mode,
                mobile_wait_ms=args.mobile_wait_ms,
                v2_max_steps=args.v2_max_steps,
                v2_use_live_perception=args.v2_use_live_perception,
                blueprint_vector_backend=args.blueprint_vector_backend,
                blueprint_vector_plugin=args.blueprint_vector_plugin,
                blueprint_embedding_dim=args.blueprint_embedding_dim,
            )
        except Exception as e:
            print(f"Failed when doing task: {args.instruction}")
            print("ERROR:", e)
        return

    task_json = json.load(open(args.tasks_json, "r", encoding="utf-8"))
    tasks = task_json["tasks"] if "tasks" in task_json else task_json

    perceptor = Perceptor(ADB_PATH, perception_args=default_perceptor_args)
    run_log_dir = f"{args.log_root}/{args.run_name}"
    os.makedirs(run_log_dir, exist_ok=True)

    if args.setting == "individual":
        persistent_heuristics_path = None
        persistent_skills_path = None
    elif args.setting == "evolution":
        persistent_heuristics_path = os.path.join(run_log_dir, "persistent_heuristics.txt")
        persistent_skills_path = os.path.join(run_log_dir, "persistent_skills.json")

        if args.specified_heuristics_path is not None:
            shutil.copy(args.specified_heuristics_path, persistent_heuristics_path)
        elif not os.path.exists(persistent_heuristics_path):
            with open(persistent_heuristics_path, "w", encoding="utf-8") as f:
                f.write(INIT_HEURISTICS)

        if args.specified_skills_path is not None:
            shutil.copy(args.specified_skills_path, persistent_skills_path)
        elif not os.path.exists(persistent_skills_path):
            with open(persistent_skills_path, "w", encoding="utf-8") as f:
                json.dump(INIT_SKILLS, f, indent=4)
    else:
        raise ValueError("Invalid setting:", args.setting)

    error_tasks = []
    print(f"INFO: Running tasks from {args.tasks_json} using {args.setting} setting ...")
    for i, task in enumerate(tasks):
        future_tasks = [t["instruction"] for t in tasks[i + 1 :]]
        print("\n\n### Running on task:", task["instruction"])
        print("\n\n")

        instruction = task["instruction"]
        if "task_id" in task:
            task_id = task["task_id"]
        else:
            task_id = args.tasks_json.split("/")[-1].split(".")[0] + f"_{args.setting}_{i}"

        try:
            _run_with_mode(
                args.runtime_mode,
                instruction=instruction,
                future_tasks=future_tasks,
                log_root=args.log_root,
                run_name=args.run_name,
                task_id=task_id,
                heuristics_path=args.specified_heuristics_path,
                skills_path=args.specified_skills_path,
                persistent_heuristics_path=persistent_heuristics_path,
                persistent_skills_path=persistent_skills_path,
                perceptor=perceptor,
                perception_args=default_perceptor_args,
                max_itr=args.max_itr,
                max_consecutive_failures=args.max_consecutive_failures,
                max_repetitive_actions=args.max_repetitive_actions,
                overwrite_log_dir=args.overwrite_task_log_dir,
                err_to_planner_thresh=2,
                enable_experience_retriever=args.enable_experience_retriever,
                temperature=args.temperature,
                screenrecord=args.screenrecord,
                v2_skip_legacy=args.v2_skip_legacy,
                guard_policy_path=args.guard_policy_path,
                guard_policy_reload_interval=args.guard_policy_reload_interval,
                watchdog_policy_path=args.watchdog_policy_path,
                watchdog_policy_reload_interval=args.watchdog_policy_reload_interval,
                session_id=args.session_id,
                strict_event_schema=args.strict_event_schema,
                status_timeline_max_events=args.status_timeline_max_events,
                web_max_steps=args.web_max_steps,
                web_replan_max_attempts=args.web_replan_max_attempts,
                confirm_wait_timeout=args.confirm_wait_timeout,
                confirm_poll_interval=args.confirm_poll_interval,
                mobile_execution_mode=args.mobile_execution_mode,
                mobile_wait_ms=args.mobile_wait_ms,
                v2_max_steps=args.v2_max_steps,
                v2_use_live_perception=args.v2_use_live_perception,
                blueprint_vector_backend=args.blueprint_vector_backend,
                blueprint_vector_plugin=args.blueprint_vector_plugin,
                blueprint_embedding_dim=args.blueprint_embedding_dim,
            )
            print("\n\nDONE:", task["instruction"])
            print("IMPORTANT: Please reset the device as needed before running the next task!")
            input("Press Enter to continue to next task ...")
        except Exception as e:
            print(f"Failed when doing task: {instruction}")
            print("ERROR:", e)
            error_tasks.append(task_id)

    error_task_output_path = f"{run_log_dir}/error_tasks.json"
    with open(error_task_output_path, "w", encoding="utf-8") as f:
        json.dump(error_tasks, f, indent=4)


if __name__ == "__main__":
    main()
