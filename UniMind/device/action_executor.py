from UniMind.perception.text_localization import ocr
from .controller import tap, swipe, type, back, home, switch_app, enter, save_screenshot_to_file, long_press, ensure_adb_keyboard_active

import time
import os
from UniMind.agents.base import  ATOMIC_ACTION_SIGNITURES
from UniMind.agents.utils.json_utils import extract_json_object_robust
from UniMind.agents.base import InfoPool
from UniMind.utils.api_client import repair_json_with_llm

def execute_atomic_action(self, action: str, arguments: dict, **kwargs) -> None:
        adb_path = self.adb
        
        if "Open_App".lower() == action.lower():
            screenshot_file = kwargs["screenshot_file"]
            ocr_detection = kwargs["ocr_detection"]
            ocr_recognition = kwargs["ocr_recognition"]
            app_name = arguments["app_name"].strip()
            text, coordinate = ocr(screenshot_file, ocr_detection, ocr_recognition)
            for ti in range(len(text)):
                if app_name == text[ti]:
                    name_coordinate = [int((coordinate[ti][0] + coordinate[ti][2])/2), int((coordinate[ti][1] + coordinate[ti][3])/2)]
                    tap(adb_path, name_coordinate[0], name_coordinate[1]- int(coordinate[ti][3] - coordinate[ti][1]))# 
                    break
            if app_name in ['Fandango', 'Walmart', 'Best Buy']:
                # additional wait time for app loading
                time.sleep(5)
            time.sleep(5)
        
        elif "Tap".lower() == action.lower():
            x, y = int(arguments["x"]), int(arguments["y"])
            tap(adb_path, x, y)
            time.sleep(2)
        
        elif "Swipe".lower() == action.lower():
            x1, y1, x2, y2 = int(arguments["x1"]), int(arguments["y1"]), int(arguments["x2"]), int(arguments["y2"])
            swipe(adb_path, x1, y1, x2, y2)
            time.sleep(2)
            
        elif "Type".lower() == action.lower():
            text = arguments["text"]
            # 在输入文本前确保ADB键盘被激活
            print("检查并确保ADB键盘激活...")
            keyboard_active = ensure_adb_keyboard_active(adb_path)
            if not keyboard_active:
                print("警告: ADB键盘未激活，文本输入可能失败")
            
            type(adb_path, text)
            time.sleep(2)

        elif "Enter".lower() == action.lower():
            enter(adb_path)
            time.sleep(2)

        elif "Back".lower() == action.lower():
            back(adb_path)
            time.sleep(2)   
        
        elif "Home".lower() == action.lower():
            home(adb_path)
            time.sleep(2)
        
        elif "Switch_App".lower() == action.lower():
            switch_app(adb_path)
            time.sleep(2)
        
        elif "Wait".lower() == action.lower():
            time.sleep(5)

        elif "Long_press".lower() == action.lower():
            x, y = int(arguments["x"]), int(arguments["y"])
            long_press(adb_path, x, y)
            time.sleep(2) # 等待文本选择菜单弹出
        
        
def execute(self, action_str: str, info_pool: InfoPool, screenshot_log_dir=None, iter="", **kwargs) -> None:
        # 使用增强的JSON解析功能
        action_object = extract_json_object_robust(action_str, "dict", ATOMIC_ACTION_SIGNITURES)
        
        if action_object is None:
            print("Error! Invalid JSON for executing action: ", action_str)
            print("尝试使用LLM进行JSON修复...")
            
            # 如果有get_model_api_response函数，尝试使用LLM修复
            if 'get_model_api_response' in kwargs:
                try:
                    
                    action_object = repair_json_with_llm(
                        broken_json=action_str,
                        atomic_actions=ATOMIC_ACTION_SIGNITURES,
                        model=kwargs.get('repair_model', 'gpt-4o-mini'),
                        get_model_api_response_func=kwargs['get_model_api_response']
                    )
                    
                    if action_object:
                        print(f"LLM JSON修复成功：{action_object}")
                    else:
                        print("LLM JSON修复失败")
                        
                except Exception as e:
                    print(f"LLM JSON修复过程中出错：{e}")
            
            if action_object is None:
                return None, 0, None
                
        action, arguments = action_object["name"], action_object["arguments"]
        action = action.strip()

        # execute atomic action
        if action in ATOMIC_ACTION_SIGNITURES:
            print("Executing atomic action: ", action, arguments)
            self.execute_atomic_action(action, arguments, info_pool=info_pool, **kwargs)
            if screenshot_log_dir is not None:
                time.sleep(1)
                screenshot_file = os.path.join(screenshot_log_dir, f"{iter}__{action.replace(' ', '')}.png")
                save_screenshot_to_file(self.adb, screenshot_file)
            return action_object, 1, None # number of atomic actions executed
        # execute skill
        elif action in info_pool.skills:
            print("Executing skill: ", action)
            skill = info_pool.skills[action]
            
            # 检查skill中是否包含Type操作，如果包含则提前激活ADB键盘
            has_type_action = any(atomic_action["name"].lower() == "type" for atomic_action in skill["atomic_action_sequence"])
            if has_type_action:
                print("Skill包含文本输入操作，提前检查并确保ADB键盘激活...")
                keyboard_active = ensure_adb_keyboard_active(self.adb)
                if not keyboard_active:
                    print("警告: ADB键盘未激活，skill中的文本输入可能失败")
            
            for i, atomic_action in enumerate(skill["atomic_action_sequence"]):
                try:
                    atomic_action_name = atomic_action["name"]
                    if atomic_action["arguments_map"] is None or len(atomic_action["arguments_map"]) == 0:
                        atomic_action_args = None
                    else:
                        atomic_action_args = {}
                        for atomic_arg_key, value in atomic_action["arguments_map"].items():
                            if value in arguments: # if the mapped key is in the skill arguments
                                atomic_action_args[atomic_arg_key] = arguments[value]
                            else: # if not: the values are directly passed
                                atomic_action_args[atomic_arg_key] = value
                    print(f"\t Executing sub-step {i}:", atomic_action_name, atomic_action_args, "...")
                    self.execute_atomic_action(atomic_action_name, atomic_action_args, info_pool=info_pool, **kwargs)
                    # log screenshot during skill execution
                    if screenshot_log_dir is not None:
                        time.sleep(1)
                        screenshot_file = os.path.join(screenshot_log_dir, f"{iter}__{action.replace(' ', '')}__{i}-{atomic_action_name.replace(' ', '')}.png")
                        save_screenshot_to_file(self.adb, screenshot_file)
                        
                except Exception as e:
                    e += f"\nError in executing step {i}: {atomic_action_name} {atomic_action_args}"
                    print("Error in executing skill: ", action, e)
                    return action_object, i, e
            return action_object, len(skill["atomic_action_sequence"]), None
        else:
            if action.lower() in ["null", "none", "finish", "exit", "stop"]:
                print("Agent choose to finish the task. Action: ", action)
            else:
                print("Error! Invalid action name: ", action)
            info_pool.finish_thought = info_pool.last_action_thought
            return None, 0, None