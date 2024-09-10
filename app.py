import uuid
import json
import time
import os
import random
import re
import requests
import tiktoken
from flask import Flask, request, Response, stream_with_context, jsonify
from flask_cors import CORS
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

executor = ThreadPoolExecutor(max_workers=10)

@lru_cache(maxsize=10)
def read_file(filename):
    """
    读取指定文件的内容，并将其作为字符串返回。

    此方法读取指定文件的完整内容，处理可能发生的异常，例如文件未找到或一般输入/输出错误，
    在出错的情况下返回空字符串。

    参数:
        filename (str): 要读取的文件名。

    返回：
        str: 文件的内容。如果文件未找到或发生错误，返回空字符串。
    """
    try:
        with open(filename, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"文件 {filename} 未找到")
        return ""
    except Exception as e:
        print(f"读取文件 {filename} 时发生错误: {e}")
        return ""

def get_env_or_file(env_var, filename):
    """
    从环境变量中获取值，如果未找到则从文件中读取。

    这有助于提高配置的灵活性，值可以从用于部署的环境变量或用于本地开发设置的文件中获取。

    参数:
        env_var (str): 要检查的环境变量。
        filename (str): 如果环境变量不存在，则要读取的文件。

    返回：
        str: 从环境变量或文件中获取的值（如果未找到）。
    """
    return os.getenv(env_var, read_file(filename))

NOTDIAMOND_URLS = [
    'https://chat.notdiamond.ai',
    'https://chat.notdiamond.ai/mini-chat'
]

def get_notdiamond_url():
    """
    从预定义的 NOTDIAMOND_URLS 列表中随机选择一个 URL。

    该函数通过从可用 URL 列表中随机选择一个 URL 来提供负载均衡，这对于将请求分配到多个端点很有用。

    返回：
        str: 随机选择的 URL 字符串。
    """
    return random.choice(NOTDIAMOND_URLS)

@lru_cache(maxsize=1)
def get_notdiamond_headers():
    """
    构造并返回调用 notdiamond API 所需的请求头。

    使用缓存来减少重复计算。

    返回：
        dict: 包含用于请求的头信息的字典。
    """
    return {
        'accept': 'text/event-stream',
        'accept-language': 'zh-CN,zh;q=0.9',
        'content-type': 'application/json',
        'next-action': get_env_or_file('NEXT_ACTION', 'next_action.txt'),
        'user-agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/128.0.0.0 Safari/537.36'),
        'cookie': get_env_or_file('COOKIES', 'cookies.txt')
    }

MODEL_INFO = {
    "gpt-4-turbo-2024-04-09": {
        "provider": "openai",
        "mapping": "gpt-4-turbo-2024-04-09"
    },
    "gemini-1.5-pro-exp-0801": {
        "provider": "google",
        "mapping": "models/gemini-1.5-pro-exp-0801"
    },
    "Meta-Llama-3.1-70B-Instruct-Turbo": {
        "provider": "togetherai",
        "mapping": "meta.llama3-1-70b-instruct-v1:0"
    },
    "Meta-Llama-3.1-405B-Instruct-Turbo": {
        "provider": "togetherai",
        "mapping": "meta.llama3-1-405b-instruct-v1:0"
    },
    "llama-3.1-sonar-large-128k-online": {
        "provider": "perplexity",
        "mapping": "llama-3.1-sonar-large-128k-online"
    },
    "gemini-1.5-pro-latest": {
        "provider": "google",
        "mapping": "models/gemini-1.5-pro-latest"
    },
    "claude-3-5-sonnet-20240620": {
        "provider": "anthropic",
        "mapping": "anthropic.claude-3-5-sonnet-20240620-v1:0"
    },
    "claude-3-haiku-20240307": {
        "provider": "anthropic",
        "mapping": "anthropic.claude-3-haiku-20240307-v1:0"
    },
    "gpt-4o-mini": {
        "provider": "openai",
        "mapping": "gpt-4o-mini"
    },
    "gpt-4o": {
        "provider": "openai",
        "mapping": "gpt-4o"
    },
    "mistral-large-2407": {
        "provider": "mistral",
        "mapping": "mistral.mistral-large-2407-v1:0"
    }
}

@lru_cache(maxsize=1)
def generate_system_fingerprint():
    """
    生成并返回唯一的系统指纹。

    这个指纹用于在日志和其他跟踪机制中唯一标识会话。指纹在单次运行期间被缓存以便重复使用，从而确保在操作中的一致性。

    返回：
        str: 以 'fp_' 开头的唯一系统指纹。
    """
    return f"fp_{uuid.uuid4().hex[:10]}"

def create_openai_chunk(content, model, finish_reason=None, usage=None):
    """
    为聊天模型创建一个格式化的响应块，包含必要的元数据。

    该工具函数构建了一个完整的字典结构，代表一段对话，包括时间戳、模型信息和令牌使用信息等元数据，
    这些对于跟踪和管理聊天交互至关重要。

    参数:
        content (str): 聊天内容的消息。
        model (str): 用于生成响应的聊天模型。
        finish_reason (str, optional): 触发内容生成结束的条件。
        usage (dict, optional): 令牌使用信息。

    返回：
        dict: 一个包含元信息的字典，代表响应块。
    """
    system_fingerprint = generate_system_fingerprint()
    chunk = {
        "id": f"chatcmpl-{uuid.uuid4()}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "system_fingerprint": system_fingerprint,
        "choices": [
            {
                "index": 0,
                "delta": {"content": content} if content else {},
                "logprobs": None,
                "finish_reason": finish_reason
            }
        ]
    }
    if usage is not None:
        chunk["usage"] = usage
    return chunk


def count_tokens(text, model="gpt-3.5-turbo-0301"):
    """
    根据指定模型计算给定文本中的令牌数量。

    该函数使用 `tiktoken` 库计算令牌数量，这对于在与各种语言模型接口时了解使用情况和限制至关重要。

    参数:
        text (str): 要进行标记和计数的文本字符串。
        model (str): 用于确定令牌边界的模型。

    返回：
        int: 文本中的令牌数量。
    """
    try:
        return len(tiktoken.encoding_for_model(model).encode(text))
    except KeyError:
        return len(tiktoken.get_encoding("cl100k_base").encode(text))

def count_message_tokens(messages, model="gpt-3.5-turbo-0301"):
    """
    使用指定模型计算给定消息中的总令牌数量。

    参数:
        messages (list): 要进行标记和计数的消息列表。
        model (str): 确定标记策略的模型名称。

    返回：
        int: 所有消息中的令牌总数。
    """
    return sum(count_tokens(str(message), model) for message in messages)

def process_dollars(s):
    """
    将每个双美元符号 '$$' 替换为单个美元符号 '$'。
    
    参数:
        s (str): 要处理的字符串。
        
    返回：
        str: 处理后的替换了美元符号的字符串。
    """
    return s.replace('$$', '$')

uuid_pattern = re.compile(r'^(\w+):(.*)$')

def parse_line(line):
    """
    根据 UUID 模式解析一行文本，尝试解码 JSON 内容。

    该函数对于解析预期按特定 UUID 前缀格式传递的文本块至关重要，有助于分离出有用的 JSON 内容以便进一步处理。

    参数:
        line (str): 假定遵循 UUID 模式的一行文本。

    返回：
        tuple: 一个包含以下内容的元组：
            - dict 或 None: 如果解析成功则为解析后的 JSON 数据，如果解析失败则为 None。
            - str: 原始内容字符串。
    """
    match = uuid_pattern.match(line)
    if not match:
        return None, None
    try:
        _, content = match.groups()
        return json.loads(content), content
    except json.JSONDecodeError:
        print(f"Error processing line: {line}")
        return None, None

def extract_content(data, last_content=""):
    """
    从数据中提取和处理内容，根据之前的内容处理不同格式和更新。

    参数:
        data (dict): 要从中提取内容的数据字典。
        last_content (str, optional): 之前的内容以便附加更改，默认为空字符串。

    返回：
        str: 提取和处理后的最终内容。
    """
    if 'output' in data and 'curr' in data['output']:
        return process_dollars(data['output']['curr'])
    elif 'curr' in data:
        return process_dollars(data['curr'])
    elif 'diff' in data and isinstance(data['diff'], list):
        if len(data['diff']) > 1:
            return last_content + process_dollars(data['diff'][1])
        elif len(data['diff']) == 1:
            return last_content
    return ""

def stream_notdiamond_response(response, model):
    """
    从 notdiamond API 流式传输和处理响应内容。

    参数:
        response (requests.Response): 来自 notdiamond API 的响应对象。
        model (str): 用于聊天会话的模型标识符。

    生成：
        dict: 来自 notdiamond API 的格式化响应块。
    """
    buffer = ""
    last_content = ""

    for chunk in response.iter_content(1024):
        if chunk:
            buffer += chunk.decode('utf-8')
            lines = buffer.split('\n')
            buffer = lines.pop()
            for line in lines:
                if line.strip():
                    data, _ = parse_line(line)
                    if data:
                        content = extract_content(data, last_content)
                        if content:
                            last_content = content
                            yield create_openai_chunk(content, model)
    
    yield create_openai_chunk('', model, 'stop')

def handle_non_stream_response(response, model, prompt_tokens):
    """
    处理非流 API 响应，计算令牌使用情况并构建最终响应 JSON。

    此功能收集并结合来自非流响应的所有内容块，以生成综合的客户端响应。

    参数:
        response (requests.Response): 来自 notdiamond API 的 HTTP 响应对象。
        model (str): 用于生成响应的模型标识符。
        prompt_tokens (int): 初始用户提示中的令牌数量。

    返回：
        flask.Response: 根据 API 规范格式化的 JSON 响应，包括令牌使用情况。
    """
    full_content = ""
    total_completion_tokens = 0
    
    for chunk in stream_notdiamond_response(response, model):
        if chunk['choices'][0]['delta'].get('content'):
            full_content += chunk['choices'][0]['delta']['content']

    completion_tokens = count_tokens(full_content, model)
    total_tokens = prompt_tokens + completion_tokens

    return jsonify({
        "id": f"chatcmpl-{uuid.uuid4()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "system_fingerprint": generate_system_fingerprint(),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": full_content
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens
        }
    })

def generate_stream_response(response, model, prompt_tokens):
    """
    为服务器发送事件生成流 HTTP 响应。

    此方法负责将响应数据分块为服务器发送事件 (SSE)，以便实时更新客户端。通过流式传输文本块来提高参与度，并通过详细的令牌使用详细信息来保持问责制。

    参数:
        response (requests.Response): 来自 notdiamond API 的 HTTP 响应。
        model (str): 用于生成响应的模型。
        prompt_tokens (int): 初始用户提示中的令牌数量。

    生成：
        str: 格式化为 SSE 的 JSON 数据块，或完成指示器。
    """
    total_completion_tokens = 0
    
    for chunk in stream_notdiamond_response(response, model):
        content = chunk['choices'][0]['delta'].get('content', '')
        total_completion_tokens += count_tokens(content, model)
        
        chunk['usage'] = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": prompt_tokens + total_completion_tokens
        }
        
        yield f"data: {json.dumps(chunk)}\n\n"
    
    yield "data: [DONE]\n\n"




@app.route('/v1/models', methods=['GET'])
def proxy_models():
    models = [
        {
            "id": model_id,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "notdiamond",
            "permission": [],
            "root": model_id,
            "parent": None,
        } for model_id in MODEL_INFO.keys()
    ]
    return jsonify({
        "object": "list",
        "data": models
    })

@app.route('/v1/chat/completions', methods=['POST'])
def handle_request():
    """
    处理到 '/v1/chat/completions' 端点的 POST 请求。
    
    从请求中提取必要的数据，处理它，并与 notdiamond 服务交互。
    
    返回：
        Response: 用于流式响应或非流式响应的 Flask 响应对象。
    """
    try:
        request_data = request.get_json()
        messages = request_data.get('messages', [])
        model_id = request_data.get('model', '')
        model = MODEL_INFO.get(model_id, {}).get('mapping', model_id)
        stream = request_data.get('stream', False)

        prompt_tokens = count_message_tokens(messages, request_data.get('model', 'gpt-4o'))

        payload = {
            "messages": messages,
            "model": model,
            "stream": stream,
            "frequency_penalty": request_data.get('frequency_penalty', 0),
            "presence_penalty": request_data.get('presence_penalty', 0),
            "temperature": request_data.get('temperature', 0.8),
            "top_p": request_data.get('top_p', 1)
        }

        headers = get_notdiamond_headers()
        url = get_notdiamond_url()
        
        future = executor.submit(requests.post, url, headers=headers, json=[payload], stream=True)
        response = future.result()
        response.raise_for_status()

        if stream:
            return Response(stream_with_context(generate_stream_response(response, model_id, prompt_tokens)), content_type='text/event-stream')
        else:
            return handle_non_stream_response(response, model_id, prompt_tokens)
         
    except Exception as e:
        return jsonify({
            'error': {'message': 'Internal Server Error', 'type': 'server_error', 'param': None, 'code': None},
            'details': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
