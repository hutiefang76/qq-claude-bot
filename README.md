# QQ-Claude Bot (小芳助手)

智能 QQ 机器人，支持多种 LLM API（Claude/GLM 等），基于 NapCat 框架。

## 功能特性

### v8 核心功能
- **多 LLM 支持** - 通过环境变量切换 API（Claude/GLM/其他兼容接口）
- **Agent 循环** - 最多 5 轮自动执行命令并分析结果
- **多格式命令识别** - 兼容 `<bash>`、``` ```bash ```  和 `/bash` 三种格式
- **会话持久化** - 保存到 sessions.json，服务重启不丢失
- **文件发送** - 支持 `<send_file>` 标签直接发送文件
- **主动解决问题** - 遇到问题自己解决，不问用户选方案
- **智能压缩** - 上下文达到 80% 自动压缩并通知

### 服务器管理
- 执行 Linux 命令（安全过滤）
- Docker 容器管理
- 系统资源监控
- 服务状态检查

### 技能系统
- `/资源` - 服务器资源概览
- `/docker` - Docker 容器状态
- `/服务` - 核心服务状态
- `/网络` - 网络端口状态
- `/进程` - 高资源进程
- `/清理` - 清理系统垃圾
- `/安全` - 安全检查
- `/日志 服务名` - 查看服务日志

## 部署

### 前置要求
- Python 3.10+
- NapCat Docker 容器
- LLM API 访问（Claude 兼容接口）

### NapCat 容器部署

```bash
sudo mkdir -p /opt/napcat/data /opt/napcat/qq-data

docker run -d --name napcat --restart unless-stopped \
  -p 3000:3000 -p 3001:3001 -p 6099:6099 \
  -v /opt/napcat/data:/app/napcat/config \
  -v /opt/napcat/qq-data:/app/.config/QQ \
  -e NAPCAT_GID=1000 -e NAPCAT_UID=1000 \
  -e TZ=Asia/Shanghai \
  -e ACCOUNT=你的QQ号 \
  mlikiowa/napcat-docker:latest
```

首次需扫码登录：访问 `http://服务器IP:6099` WebUI。
设置 `ACCOUNT` 环境变量后，重启容器自动快速登录。

**持久化目录：**
- `/opt/napcat/data` → NapCat 配置（onebot11、webui.json 等）
- `/opt/napcat/qq-data` → QQ 登录 session（重启/更新不丢失）

### Bot 部署

```bash
git clone https://github.com/hutiefang76/qq-claude-bot.git /opt/qq-claude-bot
```

创建 systemd 服务：
```bash
sudo cat > /etc/systemd/system/qq-claude-bot.service << 'SERVICE'
[Unit]
Description=QQ-Claude Bot
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 -u /opt/qq-claude-bot/bot.py
Restart=always
RestartSec=10
Environment="LLM_API_URL=https://your-api-endpoint"
Environment="LLM_API_KEY=your-api-key"
Environment="LLM_MODEL=your-model-name"

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable qq-claude-bot
sudo systemctl start qq-claude-bot
```

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_URL` | LLM API 端点（Claude Messages API 兼容） | `http://127.0.0.1:8045` |
| `LLM_API_KEY` | API 密钥 | 空 |
| `LLM_MODEL` | 模型名称 | `claude-sonnet-4-5` |

支持任何 Claude Messages API 兼容接口：Anthropic 官方、智谱 GLM（`https://open.bigmodel.cn/api/anthropic`）、自建代理等。

## 使用说明

### 私聊
- 发消息 → 智能对话（自动执行命令并分析）
- `!命令` → 快捷执行
- `/status` → 会话状态
- `/clear` → 清空历史

### 群聊
- @机器人 → 自然对话
- `/群发 群名 消息` → 发群消息
- `/at 群名 消息` → 发群消息并@主人
- `/群列表` → 查看群列表

## 技术架构

- **框架**: asyncio + aiohttp
- **QQ 接口**: NapCat WebSocket + HTTP API
- **AI**: 任意 Claude Messages API 兼容接口
- **存储**: JSON 文件持久化
- **并发**: Semaphore (5 并发)
- **Agent**: 最多 5 轮命令执行 + 结果反馈循环

## 版本历史

### v8 (2026-02-08)
- 多 LLM 支持，环境变量配置
- Agent 循环（5 轮命令执行 + 分析）
- 多格式命令识别
- 中间状态发送
- `/status` 显示 API/模型信息

### v7 (2026-01-21)
- 会话持久化
- 文件发送
- 主动解决问题模式
- 上下文智能压缩

## License

MIT License
