 #!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADB键盘调试脚本 - 帮助查看设备上的输入法和应用信息
"""

import os
import subprocess
import sys

def run_adb_command(adb_path, command):
    """执行ADB命令并返回结果"""
    full_command = f"{adb_path} {command}"
    print(f"执行命令: {full_command}")
    
    try:
        result = subprocess.run(full_command, capture_output=True, text=True, shell=True)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def main():
    """主函数"""
    print("=== ADB键盘调试工具 ===")
    
    # 获取ADB路径
    adb_path = os.environ.get("ADB_PATH", "adb")
    print(f"使用ADB路径: {adb_path}")
    
    # 1. 检查设备连接
    print("\n1. 检查设备连接状态...")
    success, stdout, stderr = run_adb_command(adb_path, "devices")
    if success:
        print("设备列表:")
        for line in stdout.split('\n')[1:]:
            if line.strip():
                print(f"   {line}")
    else:
        print(f"❌ 获取设备列表失败: {stderr}")
        return
    
    # 2. 获取当前输入法
    print("\n2. 当前默认输入法...")
    success, stdout, stderr = run_adb_command(adb_path, "shell settings get secure default_input_method")
    if success:
        print(f"当前默认输入法: {stdout}")
    else:
        print(f"❌ 获取当前输入法失败: {stderr}")
    
    # 3. 获取所有可用输入法
    print("\n3. 所有可用输入法...")
    success, stdout, stderr = run_adb_command(adb_path, "shell ime list -s")
    if success:
        ime_list = [ime.strip() for ime in stdout.split('\n') if ime.strip()]
        print(f"共找到 {len(ime_list)} 个输入法:")
        for i, ime in enumerate(ime_list, 1):
            print(f"   {i}. {ime}")
            
        # 查找可能的ADB键盘
        adb_imes = [ime for ime in ime_list if 'adb' in ime.lower()]
        if adb_imes:
            print(f"\n✅ 找到可能的ADB键盘:")
            for ime in adb_imes:
                print(f"   - {ime}")
        else:
            print("\n❌ 未找到明显的ADB键盘")
    else:
        print(f"❌ 获取输入法列表失败: {stderr}")
    
    # 4. 搜索所有包含keyboard的应用
    print("\n4. 搜索包含'keyboard'的应用...")
    success, stdout, stderr = run_adb_command(adb_path, "shell pm list packages | grep -i keyboard")
    if success and stdout:
        print("包含'keyboard'的应用:")
        for line in stdout.split('\n'):
            if line.strip():
                print(f"   {line}")
    else:
        print("未找到包含'keyboard'的应用")
    
    # 5. 搜索所有包含adb的应用
    print("\n5. 搜索包含'adb'的应用...")
    success, stdout, stderr = run_adb_command(adb_path, "shell pm list packages | grep -i adb")
    if success and stdout:
        print("包含'adb'的应用:")
        for line in stdout.split('\n'):
            if line.strip():
                print(f"   {line}")
    else:
        print("未找到包含'adb'的应用")
    
    # 6. 搜索所有包含input的应用
    print("\n6. 搜索包含'input'的应用...")
    success, stdout, stderr = run_adb_command(adb_path, "shell pm list packages | grep -i input")
    if success and stdout:
        print("包含'input'的应用:")
        for line in stdout.split('\n'):
            if line.strip():
                print(f"   {line}")
    else:
        print("未找到包含'input'的应用")
    
    # 7. 获取详细的输入法信息
    print("\n7. 详细输入法信息...")
    success, stdout, stderr = run_adb_command(adb_path, "shell ime list")
    if success:
        print("详细输入法信息:")
        print(stdout)
    else:
        print(f"❌ 获取详细输入法信息失败: {stderr}")
    
    # 8. 测试ADB键盘功能
    print("\n8. 测试ADB键盘功能...")
    test_text = "Test ADB Keyboard"
    success, stdout, stderr = run_adb_command(adb_path, f'shell am broadcast -a ADB_INPUT_TEXT --es msg "{test_text}"')
    if success:
        print(f"✅ ADB键盘广播发送成功")
        print(f"测试文本: {test_text}")
        print("如果当前有输入框处于焦点状态，应该能看到测试文本")
    else:
        print(f"❌ ADB键盘广播发送失败: {stderr}")
    
    print("\n=== 调试完成 ===")
    print("请将以上信息提供给开发者以便进一步分析")

if __name__ == "__main__":
    main()
    main()