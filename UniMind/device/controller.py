# UniMind/controller.py
import os
import time
import subprocess
from PIL import Image
from time import sleep
import base64


def get_screenshot(adb_path):
    command = adb_path + " shell rm /sdcard/screenshot.png"
    subprocess.run(command, capture_output=True, text=True, shell=True)
    time.sleep(0.5)
    command = adb_path + " shell screencap -p /sdcard/screenshot.png"
    subprocess.run(command, capture_output=True, text=True, shell=True)
    time.sleep(0.5)
    command = adb_path + " pull /sdcard/screenshot.png ./screenshot"
    subprocess.run(command, capture_output=True, text=True, shell=True)
    image_path = "./screenshot/screenshot.png"
    save_path = "./screenshot/screenshot.jpg"
    image = Image.open(image_path)
    image.convert("RGB").save(save_path, "JPEG")
    os.remove(image_path)

def start_recording(adb_path):
    print("Remove existing screenrecord.mp4")
    command = adb_path + " shell rm /sdcard/screenrecord.mp4"
    subprocess.run(command, capture_output=True, text=True, shell=True)
    print("Start!")
    # Use subprocess.Popen to allow terminating the recording process later
    command = adb_path + " shell screenrecord /sdcard/screenrecord.mp4"
    process = subprocess.Popen(command, shell=True)
    return process

def end_recording(adb_path, output_recording_path):
    print("Stopping recording...")
    # Send SIGINT to stop the screenrecord process gracefully
    stop_command = adb_path + " shell pkill -SIGINT screenrecord"
    subprocess.run(stop_command, capture_output=True, text=True, shell=True)
    sleep(1)  # Allow some time to ensure the recording is stopped
    
    print("Pulling recorded file from device...")
    pull_command = f"{adb_path} pull /sdcard/screenrecord.mp4 {output_recording_path}"
    subprocess.run(pull_command, capture_output=True, text=True, shell=True)
    print(f"Recording saved to {output_recording_path}")


def save_screenshot_to_file(adb_path, file_path="screenshot.png"):
    """
    Captures a screenshot from an Android device using ADB, saves it locally, and removes the screenshot from the device.

    Args:
        adb_path (str): The path to the adb executable.

    Returns:
        str: The path to the saved screenshot, or raises an exception on failure.
    """
    # Define the local filename for the screenshot
    local_file = file_path
    
    if os.path.dirname(local_file) != "":
        os.makedirs(os.path.dirname(local_file), exist_ok=True)

    # Define the temporary file path on the Android device
    device_file = "/sdcard/screenshot.png"
    
    try:
        # print("\tRemoving existing screenshot from the Android device...")
        command = adb_path + " shell rm /sdcard/screenshot.png"
        subprocess.run(command, capture_output=True, text=True, shell=True)
        time.sleep(0.5)

        # Capture the screenshot on the device
        # print("\tCapturing screenshot on the Android device...")
        result = subprocess.run(f"{adb_path} shell screencap -p {device_file}", capture_output=True, text=True, shell=True)
        time.sleep(0.5)
        if result.returncode != 0:
            raise RuntimeError(f"Error: Failed to capture screenshot on the device. {result.stderr}")
        
        # Pull the screenshot to the local computer
        # print("\tTransferring screenshot to local computer...")
        result = subprocess.run(f"{adb_path} pull {device_file} {local_file}", capture_output=True, text=True, shell=True)
        time.sleep(0.5)
        if result.returncode != 0:
            raise RuntimeError(f"Error: Failed to transfer screenshot to local computer. {result.stderr}")
        
        # Remove the screenshot from the device
        # print("\tRemoving screenshot from the Android device...")
        result = subprocess.run(f"{adb_path} shell rm {device_file}", capture_output=True, text=True, shell=True)
        if result.returncode != 0:
            raise RuntimeError(f"Error: Failed to remove screenshot from the device. {result.stderr}")
        
        print(f"\tAtomic Operation Screenshot saved to {local_file}")
        return local_file
    
    except Exception as e:
        print(str(e))
        return None


def tap(adb_path, x, y):
    command = adb_path + f" shell input tap {x} {y}"
    subprocess.run(command, capture_output=True, text=True, shell=True)


def type(adb_path, text):
    """
    Types text on Android device using ADB broadcast method.
    Handles newlines by converting them to ENTER key events.
    """
    # Split text by newlines to handle them separately
    lines = text.replace("\\n", "\n").split("\n")
    
    for i, line in enumerate(lines):
        if line:  # Only process non-empty lines
            # Escape double quotes in the text for shell command
            escaped_line = line.replace('"', '\\"')
            command = adb_path + f' shell am broadcast -a ADB_INPUT_TEXT --es msg "{escaped_line}"'
            subprocess.run(command, capture_output=True, text=True, shell=True)
        
        # Add ENTER key event after each line except the last one
        if i < len(lines) - 1:
            command = adb_path + f" shell input keyevent KEYCODE_ENTER"
            subprocess.run(command, capture_output=True, text=True, shell=True)

def enter(adb_path):
    command = adb_path + f" shell input keyevent KEYCODE_ENTER"
    subprocess.run(command, capture_output=True, text=True, shell=True)

def swipe(adb_path, x1, y1, x2, y2):
    command = adb_path + f" shell input swipe {x1} {y1} {x2} {y2} 300"
    subprocess.run(command, capture_output=True, text=True, shell=True)

def long_press(adb_path, x, y, duration_ms=1000):
    """
    Performs a long-press action at a given coordinate.
    Implemented by swiping from a point to the exact same point with a duration.
    """
    command = adb_path + f" shell input swipe {x} {y} {x} {y} {duration_ms}"
    print(f"DEBUG: Executing Long_press at ({x}, {y}) for {duration_ms}ms")
    subprocess.run(command, capture_output=True, text=True, shell=True)


def back(adb_path):
    command = adb_path + f" shell input keyevent 4"
    subprocess.run(command, capture_output=True, text=True, shell=True)
    
    
def home(adb_path):
    # command = adb_path + f" shell am start -a android.intent.action.MAIN -c android.intent.category.HOME"
    command = adb_path + f" shell input keyevent KEYCODE_HOME"
    subprocess.run(command, capture_output=True, text=True, shell=True)

def switch_app(adb_path):
    command = adb_path + f" shell input keyevent KEYCODE_APP_SWITCH"
    subprocess.run(command, capture_output=True, text=True, shell=True)


def ensure_adb_keyboard_active(adb_path):
    """
    确保ADB键盘处于激活状态
    
    Returns:
    - bool: True if ADB keyboard is active, False otherwise
    """
    # 检查当前输入法
    command = adb_path + " shell settings get secure default_input_method"
    result = subprocess.run(command, capture_output=True, text=True, shell=True)
    current_ime = result.stdout.strip()
    
    print(f"当前输入法: {current_ime}")
    
    # 检查是否是ADB键盘
    if "adbkeyboard" in current_ime.lower():
        print("ADB键盘已激活")
        return True
    
    # 尝试激活ADB键盘
    print("尝试激活ADB键盘...")
    
    # 首先查找可用的ADB键盘
    adb_ime = find_adb_keyboard_ime(adb_path)
    
    if adb_ime:
        print(f"找到ADB键盘: {adb_ime}")
        
        # 先启用ADB键盘
        print(f"启用ADB键盘: {adb_ime}")
        command = adb_path + f" shell ime enable {adb_ime}"
        result = subprocess.run(command, capture_output=True, text=True, shell=True)
        if result.returncode != 0:
            print(f"启用失败: {result.stderr.strip()}")
        else:
            print("启用成功")
        
        # 设置为默认输入法
        print(f"设置ADB键盘为默认: {adb_ime}")
        command = adb_path + f" shell ime set {adb_ime}"
        result = subprocess.run(command, capture_output=True, text=True, shell=True)
        
        if result.returncode == 0:
            print(f"✅ 成功设置ADB键盘为默认输入法")
            time.sleep(2)  # 等待输入法切换
            
            # 验证切换是否成功
            command = adb_path + " shell settings get secure default_input_method"
            result = subprocess.run(command, capture_output=True, text=True, shell=True)
            new_ime = result.stdout.strip()
            print(f"验证当前输入法: {new_ime}")
            
            if "adbkeyboard" in new_ime.lower():
                print("✅ ADB键盘切换成功")
                return True
            else:
                print("❌ ADB键盘切换失败")
        else:
            print(f"设置失败: {result.stderr.strip()}")
    
    # 如果没有找到，尝试常见的包名
    print("尝试常见的ADB键盘包名...")
    adb_keyboard_packages = [
        "com.android.adbkeyboard/.AdbIME",
        "com.wparam.adbkeyboard/.AdbIME", 
        "com.android.adbkeyboard/.AdbKeyboard"
    ]
    
    for package in adb_keyboard_packages:
        print(f"尝试设置输入法: {package}")
        
        # 先启用
        command = adb_path + f" shell ime enable {package}"
        result = subprocess.run(command, capture_output=True, text=True, shell=True)
        
        # 设置为默认
        command = adb_path + f" shell ime set {package}"
        result = subprocess.run(command, capture_output=True, text=True, shell=True)
        
        if result.returncode == 0:
            print(f"成功设置ADB键盘: {package}")
            time.sleep(2)  # 等待输入法切换
            
            # 验证切换是否成功
            command = adb_path + " shell settings get secure default_input_method"
            result = subprocess.run(command, capture_output=True, text=True, shell=True)
            new_ime = result.stdout.strip()
            
            if "adbkeyboard" in new_ime.lower():
                print("✅ ADB键盘切换成功")
                return True
        else:
            print(f"设置失败: {result.stderr.strip()}")
    
    print("警告: 无法激活ADB键盘，文本输入可能失败")
    return False


def get_available_input_methods(adb_path):
    """
    获取设备上可用的输入法列表
    
    Returns:
    - list: 可用输入法列表
    """
    command = adb_path + " shell ime list -s"
    result = subprocess.run(command, capture_output=True, text=True, shell=True)
    
    if result.returncode == 0:
        ime_list = [ime.strip() for ime in result.stdout.strip().split('\n') if ime.strip()]
        print(f"可用输入法: {ime_list}")
        return ime_list
    else:
        print(f"获取输入法列表失败: {result.stderr.strip()}")
        return []


def find_adb_keyboard_ime(adb_path):
    """
    查找可用的ADB键盘输入法
    
    Returns:
    - str: ADB键盘输入法包名，如果未找到返回None
    """
    ime_list = get_available_input_methods(adb_path)
    
    # 搜索包含ADB相关关键词的输入法
    adb_keywords = ['adb', 'keyboard']
    
    for ime in ime_list:
        ime_lower = ime.lower()
        if any(keyword in ime_lower for keyword in adb_keywords):
            print(f"找到ADB键盘输入法: {ime}")
            return ime
    
    print("未找到ADB键盘输入法")
    return None
