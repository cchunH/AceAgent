
import re
import json

def fix_json_with_regex(text):
    """
    使用正则表达式修复常见的JSON格式错误
    
    Parameters:
    - text (str): 包含错误JSON的文本
    
    Returns:
    - str: 修复后的JSON字符串
    """
    # 移除注释
    if "//" in text:
        text = re.sub(r'//.*', '', text)
    if "# " in text:
        text = re.sub(r'#.*', '', text)
    
    # 修复常见的JSON格式错误
    fixes = [
        # 修复数字后多余的引号（如 "y": 2191" -> "y": 2191）
        (r':\s*(\d+)"\s*([,}])', r': \1\2'),
        # 修复缺失的引号（针对键名）
        (r'(\w+):', r'"\1":'),
        # 修复单引号为双引号
        (r"'([^']*)'", r'"\1"'),
        # 修复多余的逗号
        (r',\s*}', r'}'),
        (r',\s*]', r']'),
        # 修复缺失的逗号
        (r'"\s*"', r'", "'),
        (r'}\s*"', r'}, "'),
        (r']\s*"', r'], "'),
        # 修复字符串中的换行符
        (r'"\s*\n\s*', r''),
        # 修复多余的引号
        (r'""([^"]*?)""', r'"\1"'),
        # 修复缺失的右括号/右大括号
        (r'{\s*"[^}]*$', lambda m: m.group(0) + '}'),
        # 修复字符串值前的多余引号
        (r':\s*"([^"]*)""\s*([,}])', r': "\1"\2'),
    ]
    
    for pattern, replacement in fixes:
        if callable(replacement):
            text = re.sub(pattern, replacement, text)
        else:
            text = re.sub(pattern, replacement, text)
    
    return text.strip()


def extract_json_object_robust(text, json_type="dict", atomic_actions=None):
    """
    增强版JSON提取函数，包含多层修复机制
    
    Parameters:
    - text (str): 包含JSON数据的文本
    - json_type (str): JSON结构类型 ("dict" 或 "list")
    - atomic_actions (dict): 原子操作签名，用于验证和修复
    
    Returns:
    - dict or list: 提取的JSON对象，如果失败返回None
    """
    original_text = text
    
    # 第一步：尝试原始的extract_json_object
    result = extract_json_object(text, json_type)
    if result is not None:
        return result
    
    # 第二步：使用正则表达式修复
    print("JSON解析失败，尝试正则表达式修复...")
    fixed_text = fix_json_with_regex(text)
    result = extract_json_object(fixed_text, json_type)
    if result is not None:
        print("正则表达式修复成功！")
        return result
    
    # 第三步：尝试更激进的修复策略
    print("正则表达式修复失败，尝试更激进的修复...")
    
    # 提取可能的JSON片段
    json_pattern = r"({[^{}]*})" if json_type == "dict" else r"(\[[^\[\]]*\])"
    matches = re.findall(json_pattern, text, re.DOTALL)
    
    for match in matches:
        # 尝试修复每个匹配的片段
        fixed_match = fix_json_with_regex(match)
        try:
            result = json.loads(fixed_match)
            print(f"修复成功：{fixed_match}")
            return result
        except json.JSONDecodeError:
            continue
    
    # 第四步：如果有原子操作信息，尝试智能修复
    if atomic_actions is not None:
        print("尝试基于原子操作的智能修复...")
        result = smart_json_repair(original_text, atomic_actions)
        if result is not None:
            return result
    
    print(f"所有修复尝试都失败了，原始文本：{original_text}")
    return None


def smart_json_repair(text, atomic_actions):
    """
    基于原子操作签名的智能JSON修复
    
    Parameters:
    - text (str): 原始文本
    - atomic_actions (dict): 原子操作签名
    
    Returns:
    - dict: 修复后的JSON对象，如果失败返回None
    """
    # 尝试提取动作名称
    action_names = list(atomic_actions.keys())
    found_action = None
    
    for action in action_names:
        if action.lower() in text.lower():
            found_action = action
            break
    
    if found_action is None:
        return None
    
    # 尝试提取参数
    try:
        # 查找数字（可能是坐标）
        numbers = re.findall(r'\d+', text)
        
        # 查找引号中的文本（可能是字符串参数）
        quoted_strings = re.findall(r'"([^"]*)"', text)
        
        # 根据动作类型构建JSON
        action_signature = atomic_actions[found_action]
        expected_args = action_signature['arguments']
        
        result = {"name": found_action, "arguments": {}}
        
        if len(expected_args) == 0:
            # 无参数动作
            result["arguments"] = {}
        elif len(expected_args) == 2 and all(arg in ['x', 'y'] for arg in expected_args):
            # 坐标类动作
            if len(numbers) >= 2:
                result["arguments"] = {"x": int(numbers[0]), "y": int(numbers[1])}
        elif len(expected_args) == 4 and all(arg in ['x1', 'y1', 'x2', 'y2'] for arg in expected_args):
            # 滑动类动作
            if len(numbers) >= 4:
                result["arguments"] = {
                    "x1": int(numbers[0]), "y1": int(numbers[1]),
                    "x2": int(numbers[2]), "y2": int(numbers[3])
                }
        elif 'text' in expected_args:
            # 文本输入类动作
            if quoted_strings:
                result["arguments"] = {"text": quoted_strings[0]}
                if 'x' in expected_args and 'y' in expected_args and len(numbers) >= 2:
                    result["arguments"]["x"] = int(numbers[0])
                    result["arguments"]["y"] = int(numbers[1])
        
        # 验证是否所有必需参数都已填充
        if all(arg in result["arguments"] for arg in expected_args):
            print(f"智能修复成功：{result}")
            return result
            
    except Exception as e:
        print(f"智能修复过程中出错：{e}")
    
    return None


def extract_json_object(text, json_type="dict"):
    """
    从文本字符串中提取JSON对象（原始版本，保持向后兼容）

    Parameters:
    - text (str): 包含JSON数据的文本
    - json_type (str): JSON结构类型 ("dict" 或 "list")

    Returns:
    - dict or list: 提取的JSON对象，如果失败返回None
    """
    try:
        if "//" in text:
            # Remove comments starting with //
            text = re.sub(r'//.*', '', text)
        if "# " in text:
            # Remove comments starting with #
            text = re.sub(r'#.*', '', text)
        # Try to parse the entire text as JSON
        return json.loads(text)
    except json.JSONDecodeError:
        pass  # Not a valid JSON, proceed to extract from text

    # Define patterns for extracting JSON objects or arrays
    json_pattern = r"({.*?})" if json_type == "dict" else r"(\[.*?\])"

    # Search for JSON enclosed in code blocks first
    code_block_pattern = r"```json\s*(.*?)\s*```"
    code_block_match = re.search(code_block_pattern, text, re.DOTALL)
    if code_block_match:
        json_str = code_block_match.group(1)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass  # Failed to parse JSON inside code block

    # Fallback to searching the entire text
    matches = re.findall(json_pattern, text, re.DOTALL)
    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue  # Try the next match

    # If all attempts fail, return None
    return None
