# notdiamond2api

这是一个基于 Flask 的 聊天代理服务，用于将请求转发到 chat.notdiamond.ai 服务器。

## 功能特点

- 支持多种 AI 模的映射
- 处理流式和非流式响应
- 兼容 OpenAI API 格式
- 支持 Docker Compose 部署
- 自动登录
- 自动管理 Cookie
- Token 失效自动刷新
- 一键无忧部署启动

## 支持的模型

目前支持以下模型：

- gpt-4o
- gpt-4-turbo-2024-04-09
- gpt-4o-mini
- claude-3-5-haiku-20241022
- claude-3-5-sonnet-20241022
- gemini-1.5-pro-latest
- gemini-1.5-flash-latest
- Meta-Llama-3.1-70B-Instruct-Turbo
- Meta-Llama-3.1-405B-Instruct-Turbo
- llama-3.1-sonar-large-128k-online
- mistral-large-2407

## 快速开始

1. 下载 `docker-compose.yml` 文件：

   使用 `wget` 命令：

   ```bash
   wget https://raw.com/Jiabinone/notdiamond2api/main/docker-compose.yml
   ```

   或使用 `curl` 命令：

   ```bash
   curl -O https://raw.githubusercontent.com/Jiabinone/notdiamond2api/main/docker-compose.yml
   ```

2. 确保已经设置好 Docker 环境变量，并设置启动端口：
   - `AUTH_EMAIL`：您的登录邮箱。
   - `AUTH_PASSWORD`：您的登录密码。
   - `PORT`：启动端口，默认为 3000。如需更改，请在 `docker-compose.yml` 中修改 `ports` 映射设置中的第一项。
   - `AUTH_ENABLED`: 是否启用验证。
   - `AUTH_TOKEN`: 使用的身份令牌。

3. 使用 Docker Compose 启动：

   ```
    docker-compose up -d && docker-compose logs -f
   ```

4. 服务将在 `http://localhost:3000` 上运行

## API 接口

- GET `/v1/models`：获取可用模型列表
- POST `/v1/chat/completions`：发送聊天完成请求


## 更新日志
2024-11-12
1. 更新模型映射

2024-10-14
1. 修复workers输出乱码的情况

2024-10-10
1. 修复Unauthorized的问题

2024-10-09
1. 修复workers部署失效问题
   
2024-10-08
1. 修复docker部署失效问题

2024-09-20
1. 修复登录空值问题
2. 添加 Cloudflare Workers 部署方式，支持 4 个环境变量：
   - `AUTH_ENABLED`（可选）
   - `AUTH_VALUE`（可选，需搭配 `AUTH_ENABLED`）
   - `AUTH_EMAIL`（必填）
   - `AUTH_PASSWORD`（必填）

## 许可证

本项目仅供学习使用，24小时后请删除。不得用于商业或其他目的。
