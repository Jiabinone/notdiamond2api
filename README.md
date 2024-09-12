# notdiamond2api

这是一个基于 Flask 的 AI 聊天代理服务，用于将请求转发到 chat.notdiamond.ai 服务器。

## 功能特点

- 支持多种 AI 模型的映射
- 使用 LRU 缓存优化数据读取和请求头的性能
- 处理流式和非流式响应
- 兼容 OpenAI API 格式
- 支持 Docker 部署

## 支持的模型

目前支持以下模型：

- gpt-4o
- gpt-4-turbo-2024-04-09
- gpt-4o-mini
- claude-3-haiku-20240307
- claude-3-5-sonnet-20240620
- gemini-1.5-pro-latest
- gemini-1.5-pro-exp-0801
- Meta-Llama-3.1-70B-Instruct-Turbo
- Meta-Llama-3.1-405B-Instruct-Turbo
- llama-3.1-sonar-large-128k-online
- mistral-large-2407

## 快速开始

1. 克隆仓库：

   ```
   git clone https://github.com/Jiabinone/notdiamond2api.git
   cd notdiamond2api
   ```

2. 确保已经设置好以下环境变量或文件：
   - `USER_ID`：唯一用户标识符或文件 `user_id.txt`。
     - 从浏览器的cookie选项中查找，找到以`ph_phc_`开头的cookie项，其中的`distinct_id`字段即为`user_id`。注意：`user_id`不应该被url编码。

   - `COOKIES`：包含 cookie 信息或文件 `cookies.txt`。
   - `NEXT_ACTION`：包含 next-action 值或文件 `next_action.txt`。

   这些信息可通过以下步骤获取：
   1. 登录 chat.notdiamond.ai
   2. 打开浏览器开发者工具（F12）
   3. 在网站上发送一个问题
   4. 在网络面板中找到对应的请求
   5. 在请求头中找到 `next-action` 和 `cookie` 的值
   6. 将这些值分别设置为 `NEXT_ACTION` 和 `COOKIES` 环境变量，或者写入到对应的文件

3. 使用 Docker Compose 启动服务：

   ```
    docker-compose up --build -d && docker-compose logs -f
   ```

4. 服务将在 `http://localhost:3000` 上运行

## API 接口

- GET `/v1/models`：获取可用模型列表
- POST `/v1/chat/completions`：发送聊天完成请求

## 配置

- 在 `app.py` 中的 `MODEL_INFO` 字典中定义模型映射
- 环境变量：
  - `PORT`：指定服务运行的端口（默认为 5000）

## 环境变量支持

在部署和运行服务时，可以通过设置以下环境变量来调整服务的配置：

- **PORT**：设置 Flask 应用运行的端口，默认为 `5000`。
- **COOKIES**：存储 cookie 信息。
- **NEXT_ACTION**：存储 next-action 值。

确保这些环境变量根据您的部署环境进行相应的设置。如果未设置环境变量，系统将尝试从 `cookies.txt` 和 `next_action.txt` 文件中读取对应的信息。

## 文件结构

- `app.py`：主应用程序代码
- `Dockerfile`：Docker 镜像构建文件
- `docker-compose.yml`：Docker Compose 配置文件
- `requirements.txt`：Python 依赖列表

## 注意事项

- 本服务仅用于代理请求，不包含实际的 AI 模型
- 定期检查和更新环境变量中的 `COOKIES` 和 `NEXT_ACTION` 值，因为它们可能会过期

## 开发指南

1. 创建并激活虚拟环境（可选但推荐）：

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # 对于 Windows 使用 venv\Scripts\activate
   ```

2. 安装依赖：

   ```bash
   pip install -r requirements.txt
   ```

3. 运行开发服务器：

   ```bash
   export FLASK_ENV=development
   flask run
   ```

   或者直接使用 Python 运行：

   ```bash
   python app.py
   ```

4. 进行代码修改和调试。

## 贡献

欢迎提交问题和拉取请求。

## 许可证

本项目仅供学习使用，24小时后请删除。不得用于商业或其他目的。
