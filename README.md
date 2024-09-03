# notdiamond2api

这是一个基于 Flask 的 AI 聊天代理服务，用于将请求转发到 chat.notdiamond.ai 服务器。

## 功能特点

- 支持多种 AI 模型的映射
- 处理流式和非流式响应
- 兼容 OpenAI API 格式
- 支持 Docker 部署

## 快速开始

1. 克隆仓库：

   ```
   git clone https://github.com/Jiabinone/notdiamond2api.git
   cd notdiamond2api
   ```

2. 创建并填写必要的配置文件：

   - `next_action.txt`：包含 next-action 值
   - `cookies.txt`：包含 cookie 信息

   获取这些值的方法：
   1. 登录 chat.notdiamond.ai
   2. 打开浏览器开发者工具（F12）
   3. 在网站上发送一个问题
   4. 在网络面板中找到对应的请求
   5. 在请求头中找到 `next-action` 和 `cookie` 的值
   6. 将这些值分别复制到 `next_action.txt` 和 `cookies.txt` 文件中
   7. 如文件不存在则在项目目录创建即可

3. 使用 Docker Compose 启动服务：

   ```
   docker-compose up --build
   ```

4. 服务将在 `http://localhost:3000` 上运行

## API 接口

- GET `/v1/models`：获取可用模型列表
- POST `/v1/chat/completions`：发送聊天完成请求

## 配置

- 在 `app.py` 中的 `MODEL_MAPPINGS` 字典中定义模型映射
- 环境变量：
  - `PORT`：指定服务运行的端口（默认为 5000）

## 文件结构

- `app.py`：主应用程序代码
- `Dockerfile`：Docker 镜像构建文件
- `docker-compose.yml`：Docker Compose 配置文件
- `requirements.txt`：Python 依赖列表
- `next_action.txt`：存储 next-action 值
- `cookies.txt`：存储 cookie 信息

## 注意事项

- 确保 `next_action.txt` 和 `cookies.txt` 文件包含正确的信息
- 本服务仅用于代理请求，不包含实际的 AI 模型
- 定期更新 `next_action.txt` 和 `cookies.txt` 中的值，因为它们可能会过期

## 贡献

欢迎提交问题和拉取请求。

## 许可证

[本项目仅供学习使用，24小时后请删除。不得用于商业或其他目的。]