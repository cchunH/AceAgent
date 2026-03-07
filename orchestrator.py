# orchestrator.py
import base64
import os
from pathlib import Path
import time
import copy
import torch
import shutil
from PIL import Image
from time import sleep
import threading
from UniMind.utils.api_client import inference_chat
from UniMind.perception.perceptor import Perceptor
from UniMind.device.controller import get_screenshot, start_recording, end_recording, ensure_adb_keyboard_active, get_available_input_methods, find_adb_keyboard_ime
from UniMind.agents import (
    InfoPool, Planner, Executor, Notetaker, VerifyCore, ExperienceRetrieverSkill, ExperienceRetrieverHeuristics,
    INIT_SKILLS, SkillLearningCore, HeuristicsLearningCore
)
# --- 新增导入 ---
from UniMind.agents.fast_track_agents import PlannerExecutor, QuickVerifier, VerificationResult
# --- 导入结束 ---
from UniMind.agents import add_response, add_response_two_image
from UniMind.agents import ATOMIC_ACTION_SIGNITURES
import json
from dataclasses import asdict
import os
from UniMind.utils.api_client import get_model_api_response
from UniMind.utils.image_utils import encode_image_to_base64_data_uri
import  config
import copy
import random
import concurrent.futures




ADB_PATH = config.paths.ADB_PATH
TEMP_DIR = config.paths.TEMP_DIR
SCREENSHOT_DIR = config.paths.SCREENSHOT_DIR
LOG_ROOT = config.paths.LOG_ROOT
DEFAULT_PERCEPTION_ARGS = config.models.perceptor.to_dict()

INIT_HEURISTICS = config.settings.INIT_HEURISTICS
SLEEP_BETWEEN_STEPS = config.settings.SLEEP_BETWEEN_STEPS

DEFAULT_MODEL = config.models.DEFAULT
EVOLUTION_MODEL = config.models.EVOLUTION
NOTETAKER_MODEL = config.models.NOTETAKER
PLANNER_MODEL = config.models.PLANNER
EXECUTOR_MODEL = config.models.EXECUTOR
VERIFIER_MODEL = config.models.VERIFIER
JSON_REPAIR_MODEL = config.models.JSON_REPAIR
# --- 新增配置 ---
FAST_TRACK_MODEL = getattr(config.models, 'FAST_TRACK_EXECUTOR', config.models.EXECUTOR)  # 如果没有定义则使用EXECUTOR作为默认值
USE_DUAL_TRACK = False  # 核心开关：True启用双轨，False退化为纯专家模式
# --- 配置结束 ---

def finish(
        info_pool: InfoPool,
        persistent_heuristics_path=None,
        persistent_skills_path=None
    ):
    
    print("Plan:", info_pool.plan)
    print("Progress Logs:")
    for i, p in enumerate(info_pool.progress_status_history):
        print(f"Step {i}:", p, "\n")
    print("Important Notes:", info_pool.important_notes)
    print("Finish Thought:", info_pool.finish_thought)
    if persistent_heuristics_path:
        print("Update persistent heuristics:", persistent_heuristics_path)
        with open(persistent_heuristics_path, "w") as f:
            f.write(info_pool.heuristics)
    if persistent_skills_path:
        print("Update persistent skills:", persistent_skills_path)
        with open(persistent_skills_path, "w") as f:
            json.dump(info_pool.skills, f, indent=4)
    # exit(0)



def run_single_task(
    instruction,
    future_tasks=[],
    run_name="test",
    log_root=f"logs/{DEFAULT_MODEL}/unimind_agent",
    task_id=None,
    heuristics_path=None,
    skills_path=None,
    persistent_heuristics_path=None, # cross tasks
    persistent_skills_path=None, # cross tasks
    perceptor: Perceptor = None,
    perception_args=DEFAULT_PERCEPTION_ARGS,
    max_itr=40,
    max_consecutive_failures=3,
    max_repetitive_actions=3,
    overwrite_log_dir=False,
    err_to_planner_thresh = 2, # 2 consecutive errors up-report to the planner
    enable_experience_retriever = False,
    temperature=0.0,
    screenrecord=False,
):
    
    # Create a thread lock for protecting InfoPool access
    info_pool_lock = threading.Lock()
    
    def _async_notetaking_worker(info_pool_snapshot: InfoPool, screenshot_file: str, notetaker_instance: Notetaker):
        """Background worker for asynchronous notetaking"""
        print("\n### [Async] NoteKeeper starting in background... ###\n")
        try:
            prompt_note = notetaker_instance.get_prompt(info_pool_snapshot)
            chat_note = notetaker_instance.init_chat()
            chat_note = add_response("user", prompt_note, chat_note, image=screenshot_file)
            output_note = get_model_api_response(chat_note, model=NOTETAKER_MODEL, temperature=temperature)
            
            if output_note:
                parsed_result_note = notetaker_instance.parse_response(output_note)
                important_notes = parsed_result_note['important_notes']
                
                # --- 关键修改：使用Orchestrator的锁来保护InfoPool ---
                with info_pool_lock:
                    info_pool.important_notes = important_notes
                    print("\n### [Async] NoteKeeper finished and updated InfoPool safely. ###\n")
            else:
                print("\n### [Async] NoteKeeper failed to get response. ###\n")

        except Exception as e:
            print(f"\n### [Async] NoteKeeper encountered an error: {e} ###\n")

    ### set up log dir ###
    if task_id is None:
        task_id = time.strftime("%Y%m%d-%H%M%S")
    log_dir = f"{log_root}/{run_name}/{task_id}"
    if os.path.exists(log_dir) and not overwrite_log_dir:
        print("The log dir already exists. And overwrite_log_dir is set to False. Skipping...")
        return
    os.makedirs(f"{log_dir}/screenshots", exist_ok=True)
    log_json_path = f"{log_dir}/steps.json"

    if screenrecord:
        # record one mp4 for each iteration
        screenrecord_dir = f"{log_dir}/screenrecords"
        os.makedirs(screenrecord_dir, exist_ok=True)
    
    # local experience save paths
    local_skills_save_path = f"{log_dir}/skills.json" # single-task setting
    local_heuristics_save_path = f"{log_dir}/heuristics.txt" # single-task setting

    ### Init Information Pool ###
    if skills_path is not None and persistent_skills_path is not None and skills_path != persistent_skills_path:
        raise ValueError("You cannot specify different skills_path and persistent_skills_path.")
    if heuristics_path is not None and persistent_heuristics_path is not None and heuristics_path != persistent_heuristics_path:
        raise ValueError("You cannot specify different heuristics_path and persistent_heuristics_path.")
    
    if skills_path:
        initial_skills = json.load(open(skills_path, "r")) # load agent collected skills
    elif persistent_skills_path:
        initial_skills = json.load(open(persistent_skills_path, "r"))
    else:
        initial_skills = copy.deepcopy(INIT_SKILLS)
    print("INFO: Initial skills:", initial_skills)
    
    
    if heuristics_path:
        heuristics = open(heuristics_path, "r").read() # load agent updated heuristics
    elif persistent_heuristics_path:
        heuristics = open(persistent_heuristics_path, "r").read()
    else:
        heuristics = copy.deepcopy(INIT_HEURISTICS) # user provided initial heuristics
    print("INFO: Initial heuristics:", heuristics)

    steps = []
    task_start_time = time.time()

    ## additional retrieval step before starting the task for selecting relevant heuristics and skills ##
    if enable_experience_retriever:
        print("### Doing retrieval on provided Heuristics and Skills ... ###")
        experience_retrieval_log = {
            "step": -1,
            "operation": "experience_retrieval",
            "original_heuristics": heuristics,
            "original_skills": initial_skills,
        }
        experience_retriever_start_time = time.time()

        # select skills
        experience_retriever_skill_prompt = None
        output_experience_retrieval_skill = None
        if len(initial_skills) > 1:
            experience_retriever_skill = ExperienceRetrieverSkill()
            experience_retriever_skill_prompt = experience_retriever_skill.get_prompt(instruction, initial_skills)
            chat_experience_retrieval_skill = experience_retriever_skill.init_chat()
            chat_experience_retrieval_skill = add_response("user", experience_retriever_skill_prompt, chat_experience_retrieval_skill, image=None)
            output_experience_retrieval_skill = get_model_api_response(chat_experience_retrieval_skill, model=EVOLUTION_MODEL, temperature=temperature)
            parsed_experience_retrieval_skill = experience_retriever_skill.parse_response(output_experience_retrieval_skill)
            selected_skill_names = parsed_experience_retrieval_skill['selected_skill_names']
            if selected_skill_names is None or selected_skill_names == []:
                initial_skills = copy.deepcopy(INIT_SKILLS)
            else:
                selected_skills = {}
                for key in selected_skill_names:
                    if key in initial_skills:
                        selected_skills[key] = initial_skills[key]
                    else:
                        print(f"WARNING: {key} is not in initial_skills.")
                if selected_skills != {}:
                    initial_skills = selected_skills
        sleep(1)
        # select heuristics
        experience_retriever_heuristics = ExperienceRetrieverHeuristics()
        experience_retrieval_heuristics_prompt = experience_retriever_heuristics.get_prompt(instruction, heuristics)
        chat_experience_retrieval_heuristics = experience_retriever_heuristics.init_chat()
        chat_experience_retrieval_heuristics = add_response("user", experience_retrieval_heuristics_prompt, chat_experience_retrieval_heuristics, image=None)
        output_experience_retrieval_heuristics = get_model_api_response(chat_experience_retrieval_heuristics, model=EVOLUTION_MODEL, temperature=temperature)
        parsed_experience_retrieval_heuristics = experience_retriever_heuristics.parse_response(output_experience_retrieval_heuristics)

        heuristics = parsed_experience_retrieval_heuristics['selected_heuristics']
        if heuristics.strip() == "None":
            heuristics = copy.deepcopy(INIT_HEURISTICS)
        
        experience_retriever_end_time = time.time()
        experience_retrieval_log["experience_retrieval_skill_prompt"] = experience_retriever_skill_prompt
        experience_retrieval_log["experience_retrieval_heuristics_prompt"] = experience_retrieval_heuristics_prompt
        experience_retrieval_log["experience_retrieval_skill_response"] = output_experience_retrieval_skill
        experience_retrieval_log["experience_retrieval_heuristics_response"] = output_experience_retrieval_heuristics
        experience_retrieval_log["selected_heuristics"] = heuristics
        experience_retrieval_log["selected_skills"] = initial_skills
        experience_retrieval_log["duration"] = experience_retriever_end_time - experience_retriever_start_time
        
        print("selected_heuristics:", heuristics)
        print("selected_skills:", initial_skills)

        steps.append(experience_retrieval_log)
        with open(log_json_path, "w") as f:
            json.dump(steps, f, indent=4)


    # init info pool
    info_pool = InfoPool(
        instruction = instruction,
        skills = initial_skills,
        heuristics = heuristics,
        future_tasks = future_tasks,
        err_to_planner_thresh=err_to_planner_thresh
    )

    ### temp dir ###
    if not os.path.exists(TEMP_DIR):
        os.mkdir(TEMP_DIR)
    else:
        shutil.rmtree(TEMP_DIR)
        os.mkdir(TEMP_DIR)
    if not os.path.exists(SCREENSHOT_DIR):
        os.mkdir(SCREENSHOT_DIR)

    # ### Check ADB Keyboard Status ###
    # print("### 检查ADB键盘状态 ###")
    # try:
    #     # 获取所有可用输入法
    #     available_imes = get_available_input_methods(ADB_PATH)
        
    #     # 查找ADB键盘
    #     adb_ime = find_adb_keyboard_ime(ADB_PATH)
        
    #     if adb_ime:
    #         print(f"✅ 检测到ADB键盘: {adb_ime}")
    #         keyboard_status = ensure_adb_keyboard_active(ADB_PATH)
    #         if keyboard_status:
    #             print("✅ ADB键盘已激活，文本输入功能正常")
    #         else:
    #             print("⚠️  ADB键盘未激活，但已安装，将在需要时自动激活")
    #     else:
    #         # 检查是否有其他可能的ADB键盘
    #         adb_related = [ime for ime in available_imes if "adb" in ime.lower() or "keyboard" in ime.lower()]
    #         if adb_related:
    #             print(f"⚠️  检测到可能的ADB键盘: {adb_related}")
    #             print("   将尝试在需要时激活")
    #         else:
    #             print("❌ 未检测到ADB键盘，请确保已安装ADB键盘应用")
    #             print("   推荐安装: https://github.com/senzhk/ADBKeyBoard")
    #             print("   或使用: adb install ADBKeyboard.apk")
    #             print("   或运行: python setup_adb_keyboard.py")
    # except Exception as e:
    #     print(f"⚠️  检查ADB键盘状态时出错: {e}")

    ### Init Agents ###
    if perceptor is None:
        # if perceptor is not initialized, create the perceptor
        perceptor = Perceptor(ADB_PATH, perception_args=perception_args)
    planner = Planner()
    executor = Executor(adb_path=ADB_PATH)
    notetaker = Notetaker()
    action_reflector = VerifyCore()
    exp_reflector_skills = SkillLearningCore()
    exp_reflector_heuristics = HeuristicsLearningCore()
    # --- 新增实例化 ---
    # 只有在启用双轨制时才需要实例化高速通道的Agent
    if USE_DUAL_TRACK:
        planner_executor = PlannerExecutor(adb_path=ADB_PATH)
        quick_verifier = QuickVerifier(perceptor=perceptor)
    # --- 实例化结束 ---

    # save initial heuristics and skills
    with open(local_heuristics_save_path, "w") as f:
        f.write(heuristics)
    with open(local_skills_save_path, "w") as f:
        json.dump(initial_skills, f, indent=4)

    ### Start the agent ###
    steps.append({
        "step": 0,
        "operation": "init",
        "instruction": instruction,
        "task_id": task_id,
        "run_name": run_name,
        "max_itr": max_itr,
        "max_consecutive_failures": max_consecutive_failures,
        "max_repetitive_actions": max_repetitive_actions,
        "future_tasks": future_tasks,
        "log_root": log_root,
        "heuristics_path": heuristics_path,
        "skills_path": skills_path,
        "persistent_heuristics_path": persistent_heuristics_path,
        "persistent_skills_path": persistent_skills_path,
        "perception_args": perception_args,
        "init_info_pool": asdict(info_pool)
    })
    with open(log_json_path, "w") as f:
        json.dump(steps, f, indent=4)

    # ------------------------- START OF NEW WHILE LOOP -------------------------
    iter = 0
    while True:
        iter += 1

        # --- 1. 共享的终止条件检查 (保持不变) ---
        if max_itr is not None and iter >= max_itr:
            print("Max iteration reached. Stopping...")
            task_end_time = time.time()
            steps.append({
                "step": iter,
                "operation": "finish",
                "finish_flag": "max_iteration",
                "max_itr": max_itr,
                "final_info_pool": asdict(info_pool),
                "task_duration": task_end_time - task_start_time,
            })
            with open(log_json_path, "w") as f:
                json.dump(steps, f, indent=4)
            return
        
        if len(info_pool.action_outcomes) >= max_consecutive_failures:
            last_k_aciton_outcomes = info_pool.action_outcomes[-max_consecutive_failures:]
            err_flags = [1 if outcome in ["B", "C"] else 0 for outcome in last_k_aciton_outcomes]
            if sum(err_flags) == max_consecutive_failures:
                print("Consecutive failures reaches the limit. Stopping...")
                task_end_time = time.time()
                steps.append({
                    "step": iter,
                    "operation": "finish",
                    "finish_flag": "max_consecutive_failures",
                    "max_consecutive_failures": max_consecutive_failures,
                    "final_info_pool": asdict(info_pool),
                    "task_duration": task_end_time - task_start_time,
                })
                with open(log_json_path, "w") as f:
                    json.dump(steps, f, indent=4)
                return
        
        if len(info_pool.action_history) >= max_repetitive_actions:
            last_k_actions = info_pool.action_history[-max_repetitive_actions:]
            last_k_actions_set = set()
            try:
                for act_obj in last_k_actions:
                    if "name" in act_obj:
                        hash_key = act_obj['name']
                    else:
                        hash_key = json.dumps(act_obj)
                    if "arguments" in act_obj:
                        if act_obj['arguments'] is not None:
                            for arg, value in act_obj['arguments'].items():
                                hash_key += f"-{arg}-{value}"
                        else:
                            hash_key += "-None"
                    print("hashable action key:", hash_key)
                    last_k_actions_set.add(hash_key)
            except:
                last_k_actions_set = set() # not stopping if there is any error
                pass
            if len(last_k_actions_set) == 1:
                repeated_action_key = last_k_actions_set.pop()
                if "Swipe" not in repeated_action_key and "Back" not in repeated_action_key:
                    print("Repetitive actions reaches the limit. Stopping...")
                    task_end_time = time.time()
                    steps.append({
                        "step": iter,
                        "operation": "finish",
                        "finish_flag": "max_repetitive_actions",
                        "max_repetitive_actions": max_repetitive_actions,
                        "final_info_pool": asdict(info_pool),
                        "task_duration": task_end_time - task_start_time,
                    })
                    with open(log_json_path, "w") as f:
                        json.dump(steps, f, indent=4)
                    return

        # --- 2. 共享的感知模块 (每次循环都需要) ---
        if screenrecord:
            cur_output_recording_path = f"{screenrecord_dir}/step_{iter}.mp4"
            recording_process = start_recording(ADB_PATH)

        # 每次循环都进行感知，确保信息最新
        screenshot_file = "./screenshot/screenshot.jpg"
        print(f"\n--- Iteration {iter}: Main Perception ---")
        perception_start_time = time.time()
        
        perception_infos, width, height = perceptor.get_perception_infos(screenshot_file, temp_file=TEMP_DIR)
        shutil.rmtree(TEMP_DIR)
        os.mkdir(TEMP_DIR)
        
        keyboard = False
        keyboard_height_limit = 0.9 * height
        for perception_info in perception_infos:
            if perception_info['coordinates'][1] < keyboard_height_limit:
                continue
            if 'ADB Keyboard' in perception_info['text']:
                keyboard = True
                break
        
        # 更新InfoPool的感知信息
        if iter == 1:
            info_pool.width = width
            info_pool.height = height
        
        info_pool.perception_infos_pre = copy.deepcopy(perception_infos)
        info_pool.keyboard_pre = keyboard

        # 记录感知日志
        save_screen_shot_path = f"{log_dir}/screenshots/{iter}.jpg"
        Image.open(screenshot_file).save(save_screen_shot_path)
        perception_end_time = time.time()
        steps.append({
            "step": iter,
            "operation": "perception",
            "screenshot": save_screen_shot_path,
            "perception_infos": perception_infos,
            "duration": perception_end_time - perception_start_time,
        })
        with open(log_json_path, "w") as f:
            json.dump(steps, f, indent=4)

        # --- 3. 核心轨道切换逻辑 ---
        if USE_DUAL_TRACK:
            # --- 3a. 进入双轨制模式 ---
            fast_track_success = False
            try:
                # --- 高速通道 ---
                print("\n--- [Fast Track] Starting... ---")
                
                # a. 一体化决策
                fast_track_response = planner_executor.decide(info_pool, screenshot_file)
                # 用高速通道的计划更新InfoPool，便于后续感知与记录
                if isinstance(fast_track_response, dict):
                    info_pool.plan = fast_track_response.get('updated_plan', info_pool.plan)
                action_sequence = fast_track_response.get('action_sequence', [])
                
                # 空序列直接视为失败，避免误报成功
                if not action_sequence:
                    print("[FastTrack][DEBUG] action_sequence is empty. Falling back to Expert Track.")
                    raise Exception("Empty action_sequence from PlannerExecutor")
                
                # b. 连续执行与步步验证
                sequence_fully_successful = True
                for i, action in enumerate(action_sequence):
                    print(f"\n--- [Fast Track] Executing action {i+1}/{len(action_sequence)}: {action.get('name', 'Unknown')} ---")
                    
                    # 备份当前截图
                    pre_screenshot_path = f"{log_dir}/screenshots/fast_track_pre_{iter}_{i}.jpg"
                    Image.open(screenshot_file).save(pre_screenshot_path)
                    print(f"[FastTrack][DEBUG] pre_screenshot: {pre_screenshot_path}")
                    
                    # 执行动作 (复用专家执行器)
                    action_object, num_atomic_actions_executed, skill_error_message = executor.execute(
                        json.dumps(action), info_pool, 
                        screenshot_file=screenshot_file, 
                        ocr_detection=perceptor.ocr_detection,
                        ocr_recognition=perceptor.ocr_recognition,
                        thought=action.get('description', 'Fast track action'),
                        screenshot_log_dir=os.path.join(log_dir, "screenshots"),
                        iter=f"{iter}_fast_{i}",
                        get_model_api_response=get_model_api_response,
                        repair_model=JSON_REPAIR_MODEL
                    )
                    
                    if action_object is None:
                        print(f"--- [Fast Track] Action {i+1} execution failed ---")
                        sequence_fully_successful = False
                        break
                    
                    # 获取新截图（强制拉取新图，避免与pre相同）
                    try:
                        get_screenshot(ADB_PATH)
                    except Exception as _:
                        pass
                    post_screenshot_path = f"{log_dir}/screenshots/fast_track_post_{iter}_{i}.jpg"
                    Image.open(screenshot_file).save(post_screenshot_path)
                    print(f"[FastTrack][DEBUG] post_screenshot: {post_screenshot_path}")
                    
                    # c. 快速验证
                    print(f"[FastTrack][DEBUG] Verifying with checkpoint: {action.get('success_checkpoint')}")
                    result = quick_verifier.verify(pre_screenshot_path, post_screenshot_path, action.get('success_checkpoint'))
                    print(f"[FastTrack][DEBUG] Verify result: {result}")
                    
                    if result != VerificationResult.SUCCESS:
                        print(f"--- [Fast Track] Action {i+1} verification failed ---")
                        sequence_fully_successful = False
                        # 记录失败信息
                        info_pool.action_history.append(action)
                        info_pool.summary_history.append(action.get('description'))
                        info_pool.action_outcomes.append("B")
                        info_pool.error_descriptions.append(f"Fast track verification failed: {result}")
                        break
                    else:
                        print(f"--- [Fast Track] Action {i+1} succeeded ---")
                        # 成功记录正向历史
                        info_pool.action_history.append(action)
                        info_pool.summary_history.append(action.get('description'))
                        info_pool.action_outcomes.append("A")
                        info_pool.error_descriptions.append("")
                        # d. 异步处理 (如果依赖度低)
                        if action.get('next_step_dependency', 'High') == 'Low':
                            print("--- [Fast Track] Starting async notetaking... ---")
                            info_pool_snapshot = copy.deepcopy(info_pool)
                            threading.Thread(
                                target=_async_notetaking_worker,
                                args=(info_pool_snapshot, screenshot_file, notetaker)
                            ).start()
                            # 记录异步分派
                            steps.append({
                                "step": iter,
                                "operation": "notetaking",
                                "execution_mode": "asynchronous",
                                "dependency_level": "Low",
                                "note": "FastTrack NoteKeeper dispatched"
                            })
                            with open(log_json_path, "w") as f:
                                json.dump(steps, f, indent=4)

                if sequence_fully_successful:
                    fast_track_success = True
                    print("--- [Fast Track] All actions succeeded! ---")

            except Exception as e:
                print(f"Fast Track failed with an exception: {e}")
                fast_track_success = False
            
            # --- 调度决策 ---
            if fast_track_success:
                print("--- [Fast Track] Succeeded. Continuing... ---")
                # 基于最新OCR和history判断是否达到完成条件
                # 简易完成判定：若action_sequence最后一次checkpoint类型为text且已成功，则认为阶段完成
                last_cp = None
                if 'action_sequence' in fast_track_response and fast_track_response['action_sequence']:
                    last_cp = fast_track_response['action_sequence'][-1].get('success_checkpoint')
                if last_cp and last_cp.get('type') in ['text'] and info_pool.action_outcomes and info_pool.action_outcomes[-1] == 'A':
                    print("--- [Fast Track] Detected terminal success by checkpoint ---")
                    info_pool.finish_thought = fast_track_response.get('thought', 'Task completed via fast track')
                    task_end_time = time.time()
                    steps.append({
                        "step": iter,
                        "operation": "finish",
                        "finish_flag": "fast_track_success",
                        "final_info_pool": asdict(info_pool),
                        "task_duration": task_end_time - task_start_time,
                    })
                    with open(log_json_path, "w") as f:
                        json.dump(steps, f, indent=4)
                    finish(
                        info_pool,
                        persistent_heuristics_path=persistent_heuristics_path,
                        persistent_skills_path=persistent_skills_path
                    )
                    if screenrecord:
                        end_recording(ADB_PATH, output_recording_path=cur_output_recording_path)
                    return
                # 否则继续循环
                continue  # 直接进入下一次高速循环
            else:
                print("--- [Fast Track] Failed. Switching to Expert Track... ---")
                # 如果高速通道失败，则在本轮迭代中，执行一次专家会诊
                # FALLTHROUGH to the expert track logic below

        # --- 3b. 执行专家会诊 (双轨失败时 或 单轨模式下) ---
        # 如果 USE_DUAL_TRACK 为 False，代码会直接从这里开始执行
        print("\n--- [Expert Track] Starting... ---")
        
        # a. 深度规划 (Planner)
        print("\n### Planner ... ###\n")
        ## check if stuck with errors for a long time ##
        info_pool.error_flag_plan = False
        if len(info_pool.action_outcomes) >= err_to_planner_thresh:
            latest_outcomes = info_pool.action_outcomes[-err_to_planner_thresh:]
            count = 0
            for outcome in latest_outcomes:
                if outcome in ["B", "C"]:
                    count += 1
            if count == err_to_planner_thresh:
                info_pool.error_flag_plan = True
        
        info_pool.prev_subgoal = info_pool.current_subgoal

        planning_start_time = time.time()
        prompt_planning = planner.get_prompt(info_pool)
        chat_planning = planner.init_chat()
        chat_planning = add_response("user", prompt_planning, chat_planning, image=screenshot_file)
        output_planning = get_model_api_response(chat_planning, model=PLANNER_MODEL, temperature=temperature)
        parsed_result_planning = planner.parse_response(output_planning)
        
        info_pool.plan = parsed_result_planning['plan']
        info_pool.current_subgoal = parsed_result_planning['current_subgoal']

        ## log ##
        planning_end_time = time.time()
        steps.append({
            "step": iter,
            "operation": "planning",
            "prompt_planning": prompt_planning,
            "error_flag_plan": info_pool.error_flag_plan,
            "raw_response": output_planning,
            "thought": parsed_result_planning['thought'],
            "plan": parsed_result_planning['plan'],
            "current_subgoal": parsed_result_planning['current_subgoal'],
            "duration": planning_end_time - planning_start_time,
        })
        print("Thought:", parsed_result_planning['thought'])
        print("Overall Plan:", info_pool.plan)
        print("Current Subgoal:", info_pool.current_subgoal)
        
        with open(log_json_path, "w") as f:
            json.dump(steps, f, indent=4)

        # b. 检查任务是否完成
        if "Finished" in info_pool.current_subgoal.strip():
            # 任务完成，进行经验反思
            print("\n### Learning Core ... ###\n")
            experience_reflection_start_time = time.time()
            
            # skills
            prompt_knowledge_skills = exp_reflector_skills.get_prompt(info_pool)
            chat_knowledge_skills = exp_reflector_skills.init_chat()
            chat_knowledge_skills = add_response("user", prompt_knowledge_skills, chat_knowledge_skills, image=None)
            output_knowledge_skills = get_model_api_response(chat_knowledge_skills, model=EVOLUTION_MODEL, temperature=temperature)
            parsed_result_knowledge_skills = exp_reflector_skills.parse_response(output_knowledge_skills)
            new_skill_str = parsed_result_knowledge_skills['new_skill']
            if new_skill_str != "None" and new_skill_str is not None:
                exp_reflector_skills.add_new_skill(new_skill_str, info_pool)
            print("New Skill:", new_skill_str)
            
            # heuristics
            prompt_knowledge_heuristics = exp_reflector_heuristics.get_prompt(info_pool)
            chat_knowledge_heuristics = exp_reflector_heuristics.init_chat()
            chat_knowledge_heuristics = add_response("user", prompt_knowledge_heuristics, chat_knowledge_heuristics, image=None)
            output_knowledge_heuristics = get_model_api_response(chat_knowledge_heuristics, model=EVOLUTION_MODEL, temperature=temperature)
            parsed_result_knowledge_heuristics = exp_reflector_heuristics.parse_response(output_knowledge_heuristics)
            updated_heuristics = parsed_result_knowledge_heuristics['updated_heuristics']
            info_pool.heuristics = updated_heuristics
            print("Updated Heuristics:", updated_heuristics)

            prompt_knowledge = [prompt_knowledge_skills, prompt_knowledge_heuristics]
            output_knowledge = [output_knowledge_skills, output_knowledge_heuristics]
            
            experience_reflection_end_time = time.time()
            steps.append({
                "step": iter,
                "operation": "experience_reflection",
                "prompt_knowledge": prompt_knowledge,
                "raw_response": output_knowledge,
                "new_skill": new_skill_str,
                "updated_heuristics": updated_heuristics,
                "duration": experience_reflection_end_time - experience_reflection_start_time,
            })
            with open(log_json_path, "w") as f:
                json.dump(steps, f, indent=4)
            
            # 保存更新的启发式和技能
            with open(local_heuristics_save_path, "w") as f:
                f.write(info_pool.heuristics)
            with open(local_skills_save_path, "w") as f:
                json.dump(info_pool.skills, f, indent=4)
            
            # 任务结束
            info_pool.finish_thought = parsed_result_planning['thought']
            task_end_time = time.time()
            steps.append({
                "step": iter,
                "operation": "finish",
                "finish_flag": "expert_success",
                "final_info_pool": asdict(info_pool),
                "task_duration": task_end_time - task_start_time,
            })
            with open(log_json_path, "w") as f:
                json.dump(steps, f, indent=4)
            finish(
                info_pool,
                persistent_heuristics_path=persistent_heuristics_path,
                persistent_skills_path=persistent_skills_path
            )
            if screenrecord:
                end_recording(ADB_PATH, output_recording_path=cur_output_recording_path)
            return

        ### Executor: Action Decision ###
        print("\n### Executor ... ###\n")
        action_decision_start_time = time.time()
        prompt_action = executor.get_prompt(info_pool)
        chat_action = executor.init_chat()
        chat_action = add_response("user", prompt_action, chat_action, image=screenshot_file)
        output_action = get_model_api_response(chat_action, model=EXECUTOR_MODEL, temperature=temperature)
        parsed_result_action = executor.parse_response(output_action)
        action_thought, action_object_str, action_description = parsed_result_action['thought'], parsed_result_action['action'], parsed_result_action['description']
        action_decision_end_time = time.time()

        info_pool.last_action_thought = action_thought
        
        ## execute the action ##
        action_execution_start_time = time.time()
        action_object, num_atomic_actions_executed, skill_error_message = executor.execute(action_object_str, info_pool, 
                        screenshot_file=screenshot_file, 
                        ocr_detection=perceptor.ocr_detection,
                        ocr_recognition=perceptor.ocr_recognition,
                        thought = action_thought,
                        screenshot_log_dir = os.path.join(log_dir, "screenshots"),
                        iter = str(iter),
                        get_model_api_response=get_model_api_response,
                        repair_model=JSON_REPAIR_MODEL  # 使用配置的JSON修复模型
                        )
        action_execution_end_time = time.time()
        if action_object is None:
            task_end_time = time.time()
            steps.append({
                "step": iter,
                "operation": "finish",
                "finish_flag": "abnormal",
                "final_info_pool": asdict(info_pool),
                "task_duration": task_end_time - task_start_time,
            })
            with open(log_json_path, "w") as f:
                json.dump(steps, f, indent=4)
            finish(
                info_pool, 
                persistent_heuristics_path = persistent_heuristics_path,
                persistent_skills_path = persistent_skills_path
            ) # 
            print("WARNING!!: Abnormal finishing:", action_object_str)
            if screenrecord:
                end_recording(ADB_PATH, output_recording_path=cur_output_recording_path)
            return

        info_pool.last_action = action_object
        info_pool.last_summary = action_description
        
        
        ## log ##
        steps.append({
            "step": iter,
            "operation": "action",
            "prompt_action": prompt_action,
            "raw_response": output_action,
            "action_object": action_object,
            "action_object_str": action_object_str,
            "action_thought": action_thought,
            "action_description": action_description,
            "duration": action_decision_end_time - action_decision_start_time,
            "execution_duration": action_execution_end_time - action_execution_start_time,
        })
        print("Action Thought:", action_thought)
        print("Action Description:", action_description)
        print("Action:", action_object)
        
        with open(log_json_path, "w") as f:
            json.dump(steps, f, indent=4)
        
        
        print("\n### Perceptor ... ###\n")
        ## perception on the next step ##
        perception_start_time = time.time()
        # last_perception_infos = copy.deepcopy(perception_infos)
        last_screenshot_file = "./screenshot/last_screenshot.jpg"
        # last_keyboard = keyboard
        if os.path.exists(last_screenshot_file):
            os.remove(last_screenshot_file)
        os.rename(screenshot_file, last_screenshot_file)
        
        perception_infos, width, height = perceptor.get_perception_infos(screenshot_file, temp_file=TEMP_DIR)
        shutil.rmtree(TEMP_DIR)
        os.mkdir(TEMP_DIR)
        
        keyboard = False
        for perception_info in perception_infos:
            if perception_info['coordinates'][1] < keyboard_height_limit:
                continue
            if 'ADB Keyboard' in perception_info['text']:
                keyboard = True
                break
        
        info_pool.perception_infos_post = perception_infos
        info_pool.keyboard_post = keyboard
        assert width == info_pool.width and height == info_pool.height # assert the screen size not changed

        ## log ##
        Image.open(screenshot_file).save(f"{log_dir}/screenshots/{iter+1}.jpg")
        perception_end_time = time.time()
        steps.append({
            "step": iter+1,
            "operation": "perception",
            "screenshot": f"{log_dir}/screenshots/{iter+1}.jpg",
            "perception_infos": perception_infos,
            "duration": perception_end_time - perception_start_time
        })
        print("Perception Infos:", perception_infos)
        with open(log_json_path, "w") as f:
            json.dump(steps, f, indent=4)
        
        ##

        print("\n### Verify Core ... ###\n")
        ### Verify: Check whether the action works as expected ###
        action_reflection_start_time = time.time()
        prompt_action_reflect = action_reflector.get_prompt(info_pool)
        chat_action_reflect = action_reflector.init_chat()
        chat_action_reflect = add_response_two_image("user", prompt_action_reflect, chat_action_reflect, [last_screenshot_file, screenshot_file])
        output_action_reflect = get_model_api_response(chat_action_reflect, model=VERIFIER_MODEL, temperature=temperature)
        parsed_result_action_reflect = action_reflector.parse_response(output_action_reflect)
        outcome, error_description, progress_status = (
            parsed_result_action_reflect['outcome'], 
            parsed_result_action_reflect['error_description'], 
            parsed_result_action_reflect['progress_status']
        )
        info_pool.progress_status_history.append(progress_status)
        action_reflection_end_time = time.time()

        if "A" in outcome: # Successful. The result of the last action meets the expectation.
            action_outcome = "A"
        elif "B" in outcome: # Failed. The last action results in a wrong page. I need to return to the previous state.
            action_outcome = "B"

            # NOTE: removing the automatic backing; always stopping at the failed state and then there will be a new perception step
            # no automatic backing
            # check how many backs to take
            action_name = action_object['name']
            if action_name in ATOMIC_ACTION_SIGNITURES:
                # back(ADB_PATH) # back one step for atomic actions
                pass
            elif action_name in info_pool.skills:
                # skill_object = info_pool.skills[action_name]
                # num_of_atomic_actions = len(skill_object['atomic_action_sequence'])
                if skill_error_message is not None:
                    error_description += f"; Error occured while executing the skill: {skill_error_message}"
                # for _ in range(num_atomic_actions_executed):
                #     back(ADB_PATH)   
            else:
                raise ValueError("Invalid action name:", action_name)

        elif "C" in outcome: # Failed. The last action produces no changes.
            action_outcome = "C"
        else:
            raise ValueError("Invalid outcome:", outcome)
        
        # update action history
        info_pool.action_history.append(action_object)
        info_pool.summary_history.append(action_description)
        info_pool.action_outcomes.append(action_outcome)
        info_pool.error_descriptions.append(error_description)
        info_pool.progress_status = progress_status

        ## log ##
        steps.append({
            "step": iter,
            "operation": "action_reflection",
            "prompt_action_reflect": prompt_action_reflect,
            "raw_response": output_action_reflect,
            "outcome": outcome,
            "error_description": error_description,
            "progress_status": progress_status,
            "duration": action_reflection_end_time - action_reflection_start_time,
        })
        print("Outcome:", action_outcome)
        print("Progress Status:", progress_status)
        print("Error Description:", error_description)
        
        with open(log_json_path, "w") as f:
            json.dump(steps, f, indent=4)
        
        ##
        
        ### NoteTaker: Record Important Content (Conditional Async Execution) ###
        if action_outcome == "A":
            # Get the dependency flag from the executor's decision
            dependency = parsed_result_action.get("next_step_dependency", "High")  # Default to High for safety

            if dependency == "High":
                # --- SYNCHRONOUS (BLOCKING) EXECUTION ---
                print("\n### [Sync] NoteKeeper starting... (High dependency) ###\n")
                notetaking_start_time = time.time()
                prompt_note = notetaker.get_prompt(info_pool)
                chat_note = notetaker.init_chat()
                chat_note = add_response("user", prompt_note, chat_note, image=screenshot_file) 
                output_note = get_model_api_response(chat_note, model=NOTETAKER_MODEL, temperature=temperature)
                if output_note:
                    parsed_result_note = notetaker.parse_response(output_note)
                    important_notes = parsed_result_note['important_notes']
                    # --- 关键修改：使用锁保护同步更新 ---
                    with info_pool_lock:
                        info_pool.important_notes = important_notes
                
                os.remove(last_screenshot_file)
                
                notetaking_end_time = time.time()
                steps.append({
                    "step": iter,
                    "operation": "notetaking",
                    "prompt_note": prompt_note,
                    "raw_response": output_note,
                    "important_notes": important_notes,
                    "duration": notetaking_end_time - notetaking_start_time,
                    "execution_mode": "synchronous",
                    "dependency_level": dependency
                })
                print("Important Notes:", important_notes)
                with open(log_json_path, "w") as f:
                    json.dump(steps, f, indent=4)

            else:  # dependency == "Low"
                # --- ASYNCHRONOUS (NON-BLOCKING) EXECUTION ---
                print("\n### [Async] NoteKeeper dispatched to background... (Low dependency) ###\n")
                # Create a snapshot of the current state for the background thread
                info_pool_snapshot = copy.deepcopy(info_pool)
                
                # Start the background thread
                threading.Thread(
                    target=_async_notetaking_worker,
                    args=(info_pool_snapshot, screenshot_file, notetaker)
                ).start()
                # The main loop DOES NOT wait and proceeds immediately.
                
                # Remove the screenshot file immediately for async execution
                os.remove(last_screenshot_file)
                
                # Log the asynchronous dispatch
                steps.append({
                    "step": iter,
                    "operation": "notetaking",
                    "execution_mode": "asynchronous",
                    "dependency_level": dependency,
                    "note": "NoteKeeper dispatched to background thread"
                })
                with open(log_json_path, "w") as f:
                    json.dump(steps, f, indent=4)

        elif action_outcome in ["B", "C"]:
            os.remove(last_screenshot_file)

        # --- 4. 共享的循环结尾 ---
        if screenrecord:
            end_recording(ADB_PATH, output_recording_path=cur_output_recording_path)
        print(f"\n--- Iteration {iter} Finished. Sleeping for {SLEEP_BETWEEN_STEPS}s ---\n")
        sleep(SLEEP_BETWEEN_STEPS)

    # ------------------------- END OF NEW WHILE LOOP -------------------------