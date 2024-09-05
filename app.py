# 导入所需的库
import uuid
import json
import time
import os
from flask import Flask, request, Response, stream_with_context, jsonify
from flask_cors import CORS
import requests
import re

# 创建Flask应用实例
app = Flask(__name__)
# 启用CORS,允许所有来源的跨域请求
CORS(app, resources={r"/*": {"origins": "*"}})

def read_next_action_from_file(filename='next_action.txt'):
    """从文件中读取next-action值"""
    with open(filename, 'r') as f:
        return f.read().strip()

def read_cookies_from_file(filename='cookies.txt'):
    """从文件中读取cookie"""
    with open(filename, 'r') as f:
        return f.read().strip()

# 定义NotDiamond API的URL和请求头
NOTDIAMOND_URL = 'https://chat.notdiamond.ai'
# 二选一
# NOTDIAMOND_URL = 'https://chat.notdiamond.ai/mini-chat';

NOTDIAMOND_HEADERS = {
    'accept': 'text/event-stream',
    'accept-language': 'zh-CN,zh;q=0.9',
    'content-type': 'application/json',
    'next-action': read_next_action_from_file(),  # 从文件读取next-action值
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'cookie': read_cookies_from_file()  # 从文件读取cookie
}

# 定义可用的模型列表
MODEL_LIST = [
    {"provider":"openai","model":"gpt-4-turbo-2024-04-09"},
    {"provider":"google","model":"gemini-1.5-pro-exp-0801"},
    {"provider":"togetherai","model":"Meta-Llama-3.1-70B-Instruct-Turbo"},
    {"provider":"togetherai","model":"Meta-Llama-3.1-405B-Instruct-Turbo"},
    {"provider":"perplexity","model":"llama-3.1-sonar-large-128k-online"},
    {"provider":"google","model":"gemini-1.5-pro-latest"},
    {"provider":"anthropic","model":"claude-3-5-sonnet-20240620"},
    {"provider":"anthropic","model":"claude-3-haiku-20240307"},
    {"provider":"openai","model":"gpt-4o-mini"},
    {"provider":"openai","model":"gpt-4o"},
    {"provider":"mistral","model":"mistral-large-2407"}
]

# 定义模型名称映射
MODEL_MAPPINGS = {
    "gpt-4o": "gpt-4o",
    "gpt-4-turbo-2024-04-09": "gpt-4-turbo-2024-04-09",
    "gpt-4o-mini": "gpt-4o-mini",
    "claude-3-haiku-20240307": "anthropic.claude-3-haiku-20240307-v1:0",
    "claude-3-5-sonnet-20240620": "anthropic.claude-3-5-sonnet-20240620-v1:0",
    "gemini-1.5-pro-latest": "models/gemini-1.5-pro-latest",
    "gemini-1.5-pro-exp-0801": "models/gemini-1.5-pro-exp-0801",
    "Meta-Llama-3.1-70B-Instruct-Turbo": "meta.llama3-1-70b-instruct-v1:0",
    "Meta-Llama-3.1-405B-Instruct-Turbo": "meta.llama3-1-405b-instruct-v1:0",
    "llama-3.1-sonar-large-128k-online": "llama-3.1-sonar-large-128k-online",
    "mistral-large-2407": "mistral.mistral-large-2407-v1:0"
}

def generate_system_fingerprint():
    """生成系统指纹"""
    return f"fp_{uuid.uuid4().hex[:10]}"  # 生成一个10位的随机指纹

def create_openai_chunk(content, model, finish_reason=None):
    """创建OpenAI格式的响应块"""
    system_fingerprint = generate_system_fingerprint(),
    return {
        "id": f"chatcmpl-{uuid.uuid4()}",  # 生成唯一的完成ID
        "object": "chat.completion.chunk",
        "created": int(time.time()),  # 使用当前时间戳
        "model": model,
        "system_fingerprint": system_fingerprint,
        "choices": [
            {
                "index": 0,
                "delta": {"content": content} if content else {},
                "logprobs": None,
                "finish_reason": finish_reason
            }
        ],
        "usage": None
    }

def stream_notdiamond_response(response, model):
    """处理并流式传输NotDiamond的响应"""
    buffer = ""
    last_content = ""

    def process_dollars(s):
        """处理文本中的美元符号"""
        return s.replace('$$', '$')

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
                            
                            # 提取内容
                            if 'output' in data and 'curr' in data['output']:
                                content = process_dollars(data['output']['curr'])
                            elif 'curr' in data:
                                content = process_dollars(data['curr'])
                            elif 'diff' in data and isinstance(data['diff'], list) and len(data['diff']) > 1:
                                new_content = process_dollars(data['diff'][1])
                                content = last_content + new_content
                            elif 'diff' in data and isinstance(data['diff'], list) and len(data['diff']) == 1:
                                content = last_content

                            if content:
                                last_content = content
                                yield create_openai_chunk(content, model)
                        except json.JSONDecodeError:
                            print(f"Error processing line: {line}")

    # 处理最后的缓冲区内容
    if buffer.strip():
        try:
            data = json.loads(buffer)
            content = ''
            if 'output' in data and 'curr' in data['output']:
                content = process_dollars(data['output']['curr'])
            elif 'curr' in data:
                content = process_dollars(data['curr'])
            elif 'diff' in data and isinstance(data['diff'], list) and len(data['diff']) > 1:
                new_content = process_dollars(data['diff'][1])
                content = last_content + new_content
            elif 'diff' in data and isinstance(data['diff'], list) and len(data['diff']) == 1:
                content = last_content

            if content:
                yield create_openai_chunk(content, model)
        except json.JSONDecodeError:
            print(f"Error processing final buffer: {buffer}")

    yield create_openai_chunk('', model, 'stop')  # 发送结束标记

@app.route('/v1/models', methods=['GET'])
def proxy_models():
    """处理获取可用模型列表的请求"""
    return jsonify(MODEL_LIST)

@app.route('/v1/chat/completions', methods=['POST'])
def handle_request():
    """处理聊天完成请求"""
    try:
        request_data = request.get_json()
        messages = request_data.get('messages')
        model = request_data.get('model', '')
        stream = request_data.get('stream', False)
        
        # 将外部模型名称映射到内部模型标识符
        if 'model' in request_data and request_data['model'] in MODEL_MAPPINGS:
            model = MODEL_MAPPINGS[request_data['model']]

        # 构建请求负载
        payload = {
            "messages": messages,
            "model": model,
            "stream": stream,
            "frequency_penalty": request_data.get('frequency_penalty', 0),
            "presence_penalty": request_data.get('presence_penalty', 0),
            "temperature": request_data.get('temperature', 0.8),
            "top_p": request_data.get('top_p', 1)
        }

        # 设置请求头
        headers = {
            'accept': 'text/event-stream',
            'accept-language': 'zh-CN,zh;q=0.9',
            'content-type': 'application/json',
            'next-action': read_next_action_from_file(),
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
        }
        headers['cookie'] = read_cookies_from_file()
        
        # 发送请求到NotDiamond API
        response = requests.post(NOTDIAMOND_URL, headers=headers, json=[payload], stream=True)
        response.raise_for_status()

        if stream:
            # 流式响应
            def generate():
                for chunk in stream_notdiamond_response(response, model):
                    yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"

            return Response(stream_with_context(generate()), content_type='text/event-stream')
        else:
            # 非流式响应
            full_content = ""
            for chunk in stream_notdiamond_response(response, model):
                if chunk['choices'][0]['delta'].get('content'):
                    full_content += chunk['choices'][0]['delta']['content']

            return json.dumps({
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
                    "prompt_tokens": len(full_content) // 4,
                    "completion_tokens": len(full_content) // 4,
                    "total_tokens": len(full_content) // 2
                }
            }), 200, {'Content-Type': 'application/json'}

    except Exception as e:
        # 错误处理
        return json.dumps({
            'error': 'Internal Server Error',
            'details': str(e)
        }), 500, {'Content-Type': 'application/json'}

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # 获取环境变量中的端口号,默认为5000
    app.run(debug=False, host='0.0.0.0', port=port)  # 启动Flask应用