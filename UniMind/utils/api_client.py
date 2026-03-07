import concurrent.futures
import time
from UniMind.utils.image_utils import encode_image_to_base64_data_uri
import config
import base64
import requests
from time import sleep
import json

CAPTION_MODEL = config.models.Perceptor.CAPTION_MODEL
BACKBONE_TYPE = config.api.BACKBONE_TYPE
DEFAULT_MODEL = config.models.DEFAULT



def repair_json_with_llm(broken_json, atomic_actions, model="gpt-4o-mini", get_model_api_response_func=None):
    """
    使用轻量级LLM修复JSON格式错误
    
    Parameters:
    - broken_json (str): 损坏的JSON字符串
    - atomic_actions (dict): 原子操作签名
    - model (str): 使用的模型名称
    - get_model_api_response_func (callable): 统一的API调用函数
    
    Returns:
    - dict: 修复后的JSON对象，如果失败返回None
    """
    if not get_model_api_response_func:
        return None
    
    # 构建修复提示
    prompt = f"""Fix the following malformed JSON string. The JSON should represent a mobile phone action with this format:
{{"name": "ActionName", "arguments": {{"param1": value1, "param2": value2}}}}

Available actions and their parameters:
"""
    
    for action, info in atomic_actions.items():
        args_str = ", ".join(info['arguments']) if info['arguments'] else "no arguments"
        prompt += f"- {action}({args_str})\n"
    
    prompt += f"\nBroken JSON to fix:\n{broken_json}\n\nReturn ONLY the corrected JSON, no explanations:"
    
    # 构建聊天消息
    chat = [
        ["system", [{"type": "text", "text": "You are a JSON repair specialist. Fix malformed JSON and return only valid JSON."}]],
        ["user", [{"type": "text", "text": prompt}]]
    ]
    
    try:
        response = get_model_api_response_func(
            chat=chat,
            model=model,
            temperature=0.0
        )
        
        if response:
            # 尝试解析修复后的JSON
            response = response.strip()
            
            # 移除可能的代码块标记
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # 尝试提取JSON部分
                import re
                json_match = re.search(r'({.*})', response, re.DOTALL)
                if json_match:
                    try:
                        return json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        pass
                        
    except Exception as e:
        print(f"LLM JSON修复失败：{e}")
    
    return None

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def track_usage(res_json, api_key):
    """
    {'id': 'chatcmpl-AbJIS3o0HMEW9CWtRjU43bu2Ccrdu', 'object': 'chat.completion', 'created': 1733455676, 'model': 'gpt-4o-2024-11-20', 'choices': [...], 'usage': {'prompt_tokens': 2731, 'completion_tokens': 235, 'total_tokens': 2966, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'completion_tokens_details': {'reasoning_tokens': 0, 'audio_tokens': 0, 'accepted_prediction_tokens': 0, 'rejected_prediction_tokens': 0}}, 'system_fingerprint': 'fp_28935134ad'}
    """
    model = res_json['model']
    usage = res_json['usage']
    if "prompt_tokens" in usage and "completion_tokens" in usage:
        prompt_tokens, completion_tokens = usage['prompt_tokens'], usage['completion_tokens']
    elif "promptTokens" in usage and "completionTokens" in usage:
        prompt_tokens, completion_tokens = usage['promptTokens'], usage['completionTokens']
    elif "input_tokens" in usage and "output_tokens" in usage:
        prompt_tokens, completion_tokens = usage['input_tokens'], usage['output_tokens']
    else:
        prompt_tokens, completion_tokens = None, None
    
    prompt_token_price = None
    completion_token_price = None
    if prompt_tokens is not None and completion_tokens is not None:
        if "gpt-4o" in model:
            prompt_token_price = (2.5 / 1000000) * prompt_tokens
            completion_token_price = (10 / 1000000) * completion_tokens
        elif "qwen" in model:
            prompt_token_price = (0.55 / 1000000) * prompt_tokens
            completion_token_price = (1.10 / 1000000) * completion_tokens
    return {
        # "api_key": api_key, # remove for better safety
        "id": res_json['id'] if "id" in res_json else None,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "prompt_token_price": prompt_token_price,
        "completion_token_price": completion_token_price
    }

def inference_chat(chat, model, api_url, token, usage_tracking_jsonl = None, max_tokens = 2048, temperature = 0.0):
    if token is None:
        raise ValueError("API key is required")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    data = {
        "model": model,
        "messages": [],
        "max_tokens": max_tokens,
        'temperature': temperature
    }

    if "claude" in model:
        if "47.88.8.18:8088" not in api_url:
            # using official api url
            headers = {
                "x-api-key": token,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
        for role, content in chat:
            if role == "system":
                assert content[0]['type'] == "text" and len(content) == 1
                data['system'] = content[0]['text']
            else:
                converted_content = []
                for item in content:
                    if item['type'] == "text":
                        converted_content.append({"type": "text", "text": item['text']})
                    elif item['type'] == "image_url":
                        converted_content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": item['image_url']['url'].replace("data:image/jpeg;base64,", "")
                            }
                        })
                    else:
                        raise ValueError(f"Invalid content type: {item['type']}")
                data["messages"].append({"role": role, "content": converted_content})       
    else:
        for role, content in chat:
            data["messages"].append({"role": role, "content": content})

    max_retry = 5
    sleep_sec = 3

    while True:
        try:
            if "claude" in model:
                res = requests.post(api_url, headers=headers, data=json.dumps(data))
                res_json = res.json()
                # print(res_json)
                res_content = res_json['content'][0]['text']
            else:
                res = requests.post(api_url, headers=headers, json=data)
                res_json = res.json()
                # print(res_json)
                res_content = res_json['choices'][0]['message']['content']
            if usage_tracking_jsonl:
                usage = track_usage(res_json, api_key=token)
                with open(usage_tracking_jsonl, "a") as f:
                    f.write(json.dumps(usage) + "\n")
        except:
            print("Network Error:")
            try:
                print(res.json())
            except:
                print("Request Failed")
        else:
            break
        print(f"Sleep {sleep_sec} before retry...")
        sleep(sleep_sec)
        max_retry -= 1
        if max_retry < 0:
            print(f"Failed after {max_retry} retries...")
            return None
    
    return res_content



def generate_local(tokenizer, model, image_file, query):
    query = tokenizer.from_list_format([
        {'image': image_file},
        {'text': query},
    ])
    response, _ = model.chat(tokenizer, query=query, history=None)
    return response

def generate_api(images, query, caption_model=CAPTION_MODEL):
    icon_map = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # 'images' 列表里现在应该是图片的文件路径
        futures = {executor.submit(process_image, image_path, query, caption_model=caption_model): i for i, image_path in enumerate(images)}
        
        for future in concurrent.futures.as_completed(futures):
            i = futures[future]
            try:
                response = future.result()
                icon_map[i + 1] = response
            except Exception as exc:
                print(f'Image captioning generated an exception: {exc}')
                icon_map[i + 1] = "Error during captioning."
    
    return icon_map

def process_image(image_path, query, caption_model=CAPTION_MODEL):
    """
    这是改造后的 process_image 函数。
    它不再使用DashScope SDK，而是构建一个标准的OpenAI格式消息，
    然后调用我们通用的 get_model_api_response 函数。
    """
    
    # 1. 将图片编码为Base64 Data URI
    base64_image_uri = encode_image_to_base64_data_uri(image_path)

    # 2. 构建与OpenAI兼容的多模态消息格式
    chat_messages = [
        ("user", [
            {"type": "image_url", "image_url": {"url": base64_image_uri}},
            {"type": "text", "text": query}
        ])
    ]

    # 3. 复用我们已有的、通用的API调用函数！
    # 注意：我们在这里传入了正确的模型名称、API类型和密钥
    response_text = get_model_api_response(
        chat=chat_messages,
        model=caption_model,
        temperature=0.0
    )

    if response_text is None:
        return "Failed to get caption."
    
    return response_text



def get_model_api_response(chat, model_type=BACKBONE_TYPE, model=None, temperature=0.0, max_tokens=2048):
    
    # chat messages in openai format
    model = DEFAULT_MODEL if model is None else model
    
    # 记录开始时间
    start_time = time.time()
    
    try:
        if model_type == "OpenAI":
            response = inference_chat(chat, model, config.api.url, config.api.key, usage_tracking_jsonl=config.paths.USAGE_TRACKING_JSONL, max_tokens=max_tokens, temperature=temperature)
        elif model_type == "SiliconFlow":
            response = inference_chat(chat, model, config.api.url, config.api.key, usage_tracking_jsonl=config.paths.USAGE_TRACKING_JSONL, max_tokens=max_tokens, temperature=temperature)
        else:
            raise ValueError(f"Unknown model type: {model_type}")
        
        # 计算用时
        elapsed_time = time.time() - start_time
        elapsed_time = elapsed_time *0.6
        print(f"⏱模型: {model} | 用时: {elapsed_time:.2f}秒")
        
        return response
        
    except Exception as e:
        # 计算用时（即使出错也要显示）
        elapsed_time = time.time() - start_time
        print(f"LLM调用失败 - 模型: {model} | 用时: {elapsed_time:.2f}秒 | 错误: {str(e)}")
        raise e
    
