from flask import Flask, request, jsonify, Response
import requests
import json
import re
import time
import os

app = Flask(__name__)

# 定义全局模型映射列表，将外部模型名称映射到内部模型标识符
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
def read_next_action_from_file(filename='next_action.txt'):
    """从文件中读取next-action值"""
    with open(filename, 'r') as f:
        return f.read().strip()

def read_cookies_from_file(filename):
    """从文件中读取cookie"""
    with open(filename, 'r') as f:
        return f.read().strip()

def send_request(data):
    """发送请求到AI聊天服务器并处理响应"""
    url = 'https://chat.notdiamond.ai/'
    headers = {
        'accept': 'text/event-stream',
        'accept-language': 'zh-CN,zh;q=0.9',
        'content-type': 'application/json',
        'next-action': read_next_action_from_file(),
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
    }

    # 从文件读取cookie并添加到请求头
    cookies_file = 'cookies.txt'
    headers['cookie'] = read_cookies_from_file(cookies_file)
    data_list = [data]

    # 发送POST请求
    response = requests.post(url, headers=headers, data=json.dumps(obj=data_list), stream=True)
    
    # 根据是否为流式请求处理响应
    if not data.get('stream', False):
        # 非流式请求，处理完整响应
        full_response = process_response(response)
        return create_openai_response(data, full_response)
    else:
        # 流式请求，生成响应流
        def generate():
            full_content = ""
            for chunk in response.iter_lines():
                if chunk:
                    processed_chunk = process_chunk(chunk.decode('utf-8'))
                    if processed_chunk:
                        full_content += processed_chunk
                        yield f"data: {json.dumps(create_openai_response(data, processed_chunk, stream=True, is_last=False, full_content=full_content))}\n\n"
            # 发送最后一个带有usage的响应，content为空字符串
            yield f"data: {json.dumps(create_openai_response(data, '', stream=True, is_last=True, full_content=full_content))}\n\n"
            yield "data: [DONE]\n\n"
        
        return Response(generate(), content_type='text/event-stream')

def process_response(response):
    """处理非流式响应"""
    full_response = ""
    for chunk in response.iter_content(chunk_size=1024):
        if chunk:
            full_response += process_chunk(chunk.decode('utf-8'))
    return full_response

def process_chunk(text):
    """处理单个响应块"""
    text = text.strip()
    parts = text.split(':', 1)
    if len(parts) == 2 and parts[0] != '0':
        content = parts[1]
        processed_content = ""
        # 处理diff格式的内容
        if '{"diff":' in content:
            pattern = r'"diff":\[0,"([^"]*)"\]'
            match = re.search(pattern, content)
            if match:
                processed_content += match.group(1)
        # 处理curr格式的内容
        pattern = r'"curr":"([^"]*)"'
        matches = re.findall(pattern, content)
        for match in matches:
            processed_content += match
        return processed_content
    return ""

def create_openai_response(data, content, stream=False, is_last=False, full_content=None):
    """创建符合OpenAI API格式的响应"""
    response = {
        "id": "chatcmpl-" + str(hash(content))[:10],
        "object": "chat.completion.chunk" if stream else "chat.completion",
        "created": int(time.time()),
        "model": data["model"],
        "choices": [
            {
                "index": 0,
                "delta" if stream else "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop" if is_last else None
            }
        ]
    }
    # 添加usage信息（非流式或最后一个流式块）
    if not stream or is_last:
        response["usage"] = {
            "prompt_tokens": len(data["messages"][0]["content"]),
            "completion_tokens": len(full_content) if full_content is not None else len(content),
            "total_tokens": len(data["messages"][0]["content"]) + (len(full_content) if full_content is not None else len(content))
        }
    return response



@app.route('/v1/models', methods=['GET'])
def proxy_models():
    """处理获取可用模型列表的请求"""
    models = [
        {
            "id": model_id,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "openai",
            "root": model_id,
        }
        for model_id in MODEL_MAPPINGS.keys()
    ]
    return jsonify(models)

@app.route('/v1/chat/completions', methods=['POST'])
def proxy_request():
    """处理聊天完成请求"""
    data = request.json or {}
    if not isinstance(data, dict):
        data = {}
    print(data)  # 打印接收到的请求数据
    # 将外部模型名称映射到内部模型标识符
    if 'model' in data and data['model'] in MODEL_MAPPINGS:
        data['model'] = MODEL_MAPPINGS[data['model']]
    response = send_request(data)
    # 根据响应类型返回结果
    if isinstance(response, Response):
        return response
    else:
        return jsonify(response)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)