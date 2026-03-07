 #!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADB键盘安装和配置辅助脚本
"""

import os
import subprocess
import sys
import time
from pathlib import Path

def run_adb_command(adb_path, command):
    """执行ADB命令并返回结果"""
    full_command = f"{adb_path} {command}"
    print(f"执行命令: {full_command}")
    
    try:
        result = subprocess.run(full_command, capture_output=True, text=True, shell=True)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def check_device_connection(adb_path):
    """检查设备连接状态"""
    print("检查设备连接状态...")
    success, stdout, stderr = run_adb_command(adb_path, "devices")
    
    if not success:
        print(f"❌ ADB命令执行失败: {stderr}")
        return False
    
    lines = stdout.split('\n')[1:]  # 跳过标题行
    connected_devices = [line for line in lines if line.strip() and 'device' in line]
    
    if not connected_devices:
        print("❌ 未检测到连接的设备")
        print("请确保:")
        print("1. 设备已通过USB连接到电脑")
        print("2. 设备已开启USB调试")
        print("3. 已授权电脑进行调试")
        return False
    
    print(f"✅ 检测到 {len(connected_devices)} 个设备:")
    for device in connected_devices:
        print(f"   - {device}")
    return True

def check_adb_keyboard_installed(adb_path):
    """检查ADB键盘是否已安装"""
    print("检查ADB键盘安装状态...")
    
    # 首先获取所有已安装的包
    success, stdout, stderr = run_adb_command(adb_path, "shell pm list packages")
    
    if not success:
        print(f"❌ 获取应用列表失败: {stderr}")
        return False
    
    # 搜索可能的ADB键盘包名
    adb_keywords = ['adb', 'keyboard', 'input']
    potential_packages = []
    
    for line in stdout.split('\n'):
        line = line.strip()
        if line.startswith('package:'):
            package_name = line.replace('package:', '')
            # 检查是否包含ADB键盘相关关键词
            if any(keyword in package_name.lower() for keyword in adb_keywords):
                potential_packages.append(package_name)
    
    if potential_packages:
        print("✅ 检测到以下可能的ADB键盘相关应用:")
        for package in potential_packages:
            print(f"   - {package}")
        
        # 进一步检查输入法列表
        print("\n检查可用输入法...")
        success, ime_stdout, ime_stderr = run_adb_command(adb_path, "shell ime list -s")
        
        if success and ime_stdout:
            ime_list = [ime.strip() for ime in ime_stdout.split('\n') if ime.strip()]
            print("可用输入法:")
            for ime in ime_list:
                print(f"   - {ime}")
                
            # 检查是否有ADB键盘输入法
            adb_imes = [ime for ime in ime_list if 'adb' in ime.lower()]
            if adb_imes:
                print(f"\n✅ 找到ADB键盘输入法: {adb_imes}")
                return True
        
        return len(potential_packages) > 0
    else:
        print("❌ 未检测到ADB键盘应用")
        print("搜索的关键词: adb, keyboard, input")
        return False

def install_adb_keyboard(adb_path, apk_path=None):
    """安装ADB键盘"""
    if apk_path and Path(apk_path).exists():
        print(f"安装ADB键盘: {apk_path}")
        success, stdout, stderr = run_adb_command(adb_path, f"install {apk_path}")
        
        if success:
            print("✅ ADB键盘安装成功")
            return True
        else:
            print(f"❌ ADB键盘安装失败: {stderr}")
            return False
    else:
        print("❌ 未找到ADB键盘APK文件")
        print("请下载ADB键盘APK文件:")
        print("1. 从 https://github.com/senzhk/ADBKeyBoard/releases 下载")
        print("2. 或使用: wget https://github.com/senzhk/ADBKeyBoard/releases/download/v2.0/ADBKeyboard.apk")
        return False

def setup_adb_keyboard(adb_path):
    """配置ADB键盘"""
    print("配置ADB键盘...")
    
    # 常见的ADB键盘包名
    adb_keyboard_packages = [
        "com.android.adbkeyboard/.AdbIME",
        "com.wparam.adbkeyboard/.AdbIME",
        "com.android.adbkeyboard/.AdbKeyboard"
    ]
    
    # 首先获取可用的输入法
    success, stdout, stderr = run_adb_command(adb_path, "shell ime list -s")
    if not success:
        print(f"❌ 获取输入法列表失败: {stderr}")
        return False
    
    available_imes = [ime.strip() for ime in stdout.split('\n') if ime.strip()]
    print(f"可用输入法: {available_imes}")
    
    # 找到ADB键盘
    adb_ime = None
    for package in adb_keyboard_packages:
        if package in available_imes:
            adb_ime = package
            break
    
    if not adb_ime:
        print("❌ 未找到可用的ADB键盘输入法")
        return False
    
    print(f"找到ADB键盘: {adb_ime}")
    
    # 启用ADB键盘
    print("启用ADB键盘...")
    success, stdout, stderr = run_adb_command(adb_path, f"shell ime enable {adb_ime}")
    if not success:
        print(f"⚠️  启用ADB键盘失败: {stderr}")
    
    # 设置为默认输入法
    print("设置ADB键盘为默认输入法...")
    success, stdout, stderr = run_adb_command(adb_path, f"shell ime set {adb_ime}")
    
    if success:
        print("✅ ADB键盘配置成功")
        
        # 验证设置
        time.sleep(1)
        success, current_ime, stderr = run_adb_command(adb_path, "shell settings get secure default_input_method")
        if success:
            print(f"当前默认输入法: {current_ime}")
            if adb_ime in current_ime:
                print("✅ ADB键盘已成功设置为默认输入法")
                return True
        
    print(f"❌ 设置ADB键盘失败: {stderr}")
    return False

def test_adb_keyboard(adb_path):
    """测试ADB键盘功能"""
    print("测试ADB键盘功能...")
    
    # 发送测试文本
    test_text = "Hello ADB Keyboard Test"
    success, stdout, stderr = run_adb_command(adb_path, f'shell am broadcast -a ADB_INPUT_TEXT --es msg "{test_text}"')
    
    if success:
        print("✅ ADB键盘文本输入测试成功")
        print(f"测试文本: {test_text}")
        print("如果当前有输入框处于焦点状态，应该能看到测试文本")
        return True
    else:
        print(f"❌ ADB键盘文本输入测试失败: {stderr}")
        return False

def main():
    """主函数"""
    print("=== ADB键盘安装和配置工具 ===")
    
    # 获取ADB路径
    adb_path = os.environ.get("ADB_PATH", "adb")
    print(f"使用ADB路径: {adb_path}")
    
    # 检查设备连接
    if not check_device_connection(adb_path):
        return False
    
    # 检查ADB键盘是否已安装
    if not check_adb_keyboard_installed(adb_path):
        # 尝试安装ADB键盘
        apk_files = list(Path(".").glob("*ADB*eyboard*.apk")) + list(Path(".").glob("*adb*eyboard*.apk"))
        if apk_files:
            if not install_adb_keyboard(adb_path, str(apk_files[0])):
                return False
        else:
            print("请手动安装ADB键盘后重新运行此脚本")
            print("推荐下载地址: https://github.com/senzhk/ADBKeyBoard")
            print("或运行: python debug_keyboard.py 查看详细信息")
            return False
    
    # 配置ADB键盘
    if not setup_adb_keyboard(adb_path):
        return False
    
    # 测试ADB键盘
    if not test_adb_keyboard(adb_path):
        print("⚠️  ADB键盘测试失败，但配置可能仍然有效")
    
    print("\n=== 配置完成 ===")
    print("✅ ADB键盘已配置完成，现在可以进行文本输入操作")
    print("运行命令: python orchestrator.py")
    print("或运行: python test_adb_keyboard_switch.py 测试切换功能")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)