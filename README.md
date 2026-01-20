# QQ-Claude Bot

智能 QQ 机器人，基于 Claude API 和 NapCat 框架。

## 功能特性

### v7 核心功能
- 🔄 **会话持久化** - 保存到 sessions.json，服务重启不丢失
- 📤 **文件发送** - 支持 `<send_file>` 标签直接发送文件
- 🧠 **主动解决问题** - 遇到问题自己解决，不问用户选方案
- 📝 **智能压缩** - 上下文达到 80% 自动压缩并通知

### 服务器管理
- 完全控制服务器，执行任意 Linux 命令
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

## 安装部署

### 前置要求
- Python 3.10+
- NapCat (QQ 机器人框架)
- Claude API 访问

### 安装步骤

1. 克隆仓库
```bash
git clone https://github.com/hutiefang76/qq-claude-bot.git
cd qq-claude-bot
```

2. 修改配置
```bash
# 编辑 bot.py 中的配置
NAPCAT_WS = "ws://127.0.0.1:3001"
NAPCAT_HTTP = "http://127.0.0.1:3000"
CLAUDE_API = "http://your-api-endpoint"
API_KEY = "your-api-key"
ALLOWED_USERS = [你的QQ号]
```

3. 创建 systemd 服务
```bash
sudo cat > /etc/systemd/system/qq-claude-bot.service << 'SERVICE'
[Unit]
Description=QQ-Claude Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/qq-claude-bot
ExecStart=/usr/bin/python3 /opt/qq-claude-bot/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable qq-claude-bot
sudo systemctl start qq-claude-bot
```

## 使用说明

### 私聊命令
- 发送任何消息 - 智能对话
- `!命令` - 快捷执行命令
- `/status` - 查看会话状态
- `/clear` - 清空对话历史
- 技能命令 - 见上方技能列表

### 群聊功能
- @机器人 发送消息 - 自然对话
- `/群发 群名 消息` - 发送群消息
- `/at 群名 消息` - 发送群消息并@主人

## 技术架构

- **框架**: asyncio + aiohttp
- **QQ 接口**: NapCat WebSocket + HTTP API
- **AI 模型**: Claude Sonnet 4.5
- **会话存储**: JSON 文件持久化
- **并发控制**: Semaphore (5 并发)

## 配置文件

### config.json
```json
{
  "server_info": {...},
  "skills": {...},
  "command_reference": {...}
}
```

## 版本历史

### v7 (2026-01-21)
- 会话持久化到 sessions.json
- QQ 文件发送功能
- 主动解决问题模式
- 上下文智能压缩
- 历史消息 50条，token 上限 12000

### v6
- 文件发送基础功能
- 主动思考提示词优化

### v5
- 上下文压缩通知
- 主动思考模式

## 作者

**hutiefang**
- Email: hutiefang@qq.com
- WeChat: hutiefang
- QQ: 76294506

## License

MIT License
