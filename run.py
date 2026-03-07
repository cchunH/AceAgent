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
        host, port = start_global_session_runtime_server(
            host=args.session_runtime_server_host,
            port=args.session_runtime_server_port,
            persistence_path=session_state_path,
        )
        print(f"SessionRuntime API server started at http://{host}:{port}")
        print(f"SessionRuntime state path: {session_state_path}")
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
            _run_with_mode(
                args.runtime_mode,
                instruction=args.instruction,
                run_name=args.run_name,
                log_root=args.log_root,
                heuristics_path=args.specified_heuristics_path,
                skills_path=args.specified_skills_path,
                persistent_heuristics_path=persistent_heuristics_path,
                persistent_skills_path=persistent_skills_path,
                perceptor=None,
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
