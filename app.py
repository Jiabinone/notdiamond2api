import uuid
import json
import time
import os
import re
import random
import requests
import tiktoken
from flask import Flask, request, Response, stream_with_context, jsonify, abort, make_response
from flask_cors import CORS
from functools import lru_cache,wraps
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

executor = ThreadPoolExecutor(max_workers=10)

API_KEY =  "sk-liunxdo"

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('Authorization')
        if api_key and api_key == f"Bearer {API_KEY}":
            return f(*args, **kwargs)
        else:
            return jsonify({"error": "Invalid or missing API key"}), 401
    return decorated_function

# 使用LRU缓存，最大容量为10，用于缓存文件内容
@lru_cache(maxsize=10)
def read_file(filename):
    try:
        with open(filename, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"文件 {filename} 未找到")
        return ""
    except Exception as e:
        print(f"读取文件 {filename} 时发生错误: {e}")
        return ""

# 从环境变量或文件中获取信息
def get_env_or_file(env_var, filename):
    return os.environ.get(env_var) or read_file(filename)

NOTDIAMOND_URLS = [
    'https://chat.notdiamond.ai',
    'https://chat.notdiamond.ai/mini-chat'
]

# 从预设的URL列表中随机选择一个
def get_notdiamond_url():
    return random.choice(NOTDIAMOND_URLS)

# 使用LRU缓存，缓存头信息，最大容量为1
@lru_cache(maxsize=1)
def get_notdiamond_headers():
    return {
        'accept': 'text/event-stream',
        'accept-language': 'zh-CN,zh;q=0.9',
        'content-type': 'application/json',
        'next-action': get_env_or_file('NEXT_ACTION', 'next_action.txt'),
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'cookie': get_env_or_file('COOKIES', 'cookies.txt')
    }

@lru_cache(maxsize=1)
def getAuthorizationKey():
    return get_env_or_file('API_KEY', 'API_KEY.txt')

# 模型信息字典，包含各模型的提供商和映射
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

# 生成系统指纹，用于追踪和安全目的
def generate_system_fingerprint():
    return f"fp_{uuid.uuid4().hex[:10]}"

# 创建OpenAI格式的分块内容
def create_openai_chunk(content, model, finish_reason=None, usage=None):
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

# 处理带美元符号的字符串
def process_dollars(s):
    return s.replace('$$', '$')

def count_tokens(text, model="gpt-3.5-turbo-0301"):
    """计算给定文本的token数量"""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

def count_message_tokens(messages, model="gpt-3.5-turbo-0301"):
    """计算消息列表的token数量"""
    return sum(count_tokens(str(message)) for message in messages)

def stream_notdiamond_response(response, model):
    buffer = ""
    last_content = ""

    for chunk in response.iter_content(chunk_size=1024):
        if chunk:
            buffer += chunk.decode('utf-8')
            lines = buffer.split('\n')
            buffer = lines.pop()
            for line in lines:
                if line.strip():
                    match = re.match(r'^([0-9a-zA-Z]+):(.*)$', line)
                    if match:
                        try:
                            _, content = match.groups()
                            data = json.loads(content)
                            content = ''
                            if 'output' in data and 'curr' in data['output']:
                                content = process_dollars(data['output']['curr'])
                            elif 'curr' in data:
                                content = process_dollars(data['curr'])
                            elif 'diff' in data and isinstance(data['diff'], list):
                                if len(data['diff']) > 1:
                                    new_content = process_dollars(data['diff'][1])
                                    content = last_content + new_content
                                elif len(data['diff']) == 1:
                                    content = last_content

                            if content:
                                last_content = content
                                yield create_openai_chunk(content, model)
                        except json.JSONDecodeError:
                            print(f"Error processing line: {line}")  # 可考虑替换为日志记录
    
    yield create_openai_chunk('', model, 'stop')

# 处理非流式响应
def handle_non_stream_response(response, model, prompt_tokens):
    full_content = ""
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

# 生成流式响应
def generate_stream_response(response, model, prompt_tokens):
    completion_tokens = 0
    for chunk in stream_notdiamond_response(response, model):
        completion_tokens += count_tokens(chunk['choices'][0]['delta'].get('content', ''), model)
        if chunk['choices'][0]['finish_reason'] == 'stop':
            chunk['usage'] = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
        yield f"data: {json.dumps(chunk)}\n\n"
    yield "data: [DONE]\n\n"

def generate_anthropic_stream_response(response, model, message_id):
    yield f"event: message_start\ndata: {json.dumps({'type': 'message_start', 'message': {'id': message_id, 'type': 'message', 'role': 'assistant', 'model': model, 'stop_sequence': None, 'usage': {'input_tokens': 0, 'output_tokens': 0}, 'content': [], 'stop_reason': None}})}\n\n"
    
    yield f"event: content_block_start\ndata: {json.dumps({'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}})}\n\n"
    
    output_tokens = 0
    for chunk in stream_notdiamond_response(response, model):
        content = chunk['choices'][0]['delta'].get('content', '')
        if content:
            output_tokens += count_tokens(content, model)
            yield f"event: content_block_delta\ndata: {json.dumps({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': content}})}\n\n"
        
        if chunk['choices'][0]['finish_reason'] == 'stop':
            yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"
            yield f"event: message_delta\ndata: {json.dumps({'type': 'message_delta', 'delta': {'stop_reason': 'end_turn', 'stop_sequence': None}, 'usage': {'output_tokens': output_tokens}})}\n\n"
            yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"
    
    yield "data: [DONE]\n\n"

def handle_anthropic_request(request_data, stream=False):
    messages = [{"role": "user" if msg["role"] == "human" else "assistant", "content": msg["content"]} 
                for msg in request_data.get('messages', [])]
    model_id = request_data.get('model', '')
    model = MODEL_INFO.get(model_id, {}).get('mapping', model_id)
    print(model)

    # 计算输入token数
    prompt_tokens = count_message_tokens(messages, model)

    payload = {
        "messages": messages,
        "model": model,
        "stream": stream,
        "max_tokens": request_data.get('max_tokens'),
        "temperature": request_data.get('temperature', 0.8),
        "top_p": request_data.get('top_p', 1)
    }

    headers = get_notdiamond_headers()
    url = get_notdiamond_url()
    
    future = executor.submit(requests.post, url, headers=headers, json=[payload], stream=True)
    response = future.result()
    response.raise_for_status()

    return response, request_data.get('model', ''), prompt_tokens

@app.route('/v1/messages', methods=['POST'])
def handle_anthropic_messages():
    try:
        request_data = request.get_json()
        stream = request_data.get('stream', False)
        
        response, model, prompt_tokens = handle_anthropic_request(request_data, stream)
        message_id = f"msg_{uuid.uuid4()}"

        if stream:
            return Response(stream_with_context(generate_anthropic_stream_response(response, model, message_id)), 
                            content_type='text/event-stream')
        else:
            full_content = ""
            for chunk in stream_notdiamond_response(response, model):
                if chunk['choices'][0]['delta'].get('content'):
                    full_content += chunk['choices'][0]['delta']['content']

            completion_tokens = count_tokens(full_content, model)
            total_tokens = prompt_tokens + completion_tokens

            anthropic_response = {
                "id": message_id,
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": full_content}],
                "model": model,
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {
                    "input_tokens": prompt_tokens,
                    "output_tokens": completion_tokens
                }
            }

            response = make_response(jsonify(anthropic_response))
            response.headers['X-Anthropic-Version'] = '2023-06-01'
            response.headers['Content-Type'] = 'application/json'
            return response

    except Exception as e:
        return jsonify({
            'error': {'message': 'Internal Server Error', 'type': 'server_error'},
            'details': str(e)
        }), 500

# 获取模型列表的API
@app.route('/v1/models', methods=['GET'])
@require_api_key
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

# 处理请求的API
@app.route('/v1/chat/completions', methods=['POST'])
@require_api_key
def handle_request():
    try:
        request_data = request.get_json()
        messages = request_data.get('messages', [])
        model_id = request_data.get('model', '')
        model = MODEL_INFO.get(model_id, {}).get('mapping', model_id)
        stream = request_data.get('stream', False)

        # 计算输入token数
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
    if(getAuthorizationKey()):
        API_KEY = getAuthorizationKey()
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
