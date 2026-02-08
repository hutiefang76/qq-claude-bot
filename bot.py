#!/usr/bin/env python3
"""
QQ-Claude Bot v8 - 智能服务器管理助手
功能: 持久化会话 + 主动解决问题 + 文件发送
"""
import json, asyncio, aiohttp, subprocess, re, os, shutil
from collections import deque
from pathlib import Path
from datetime import datetime

# 配置
NAPCAT_WS = "ws://127.0.0.1:3001"
NAPCAT_HTTP = "http://127.0.0.1:3000"
LLM_API = os.environ.get("LLM_API_URL", "http://127.0.0.1:8045")
LLM_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-5")
ALLOWED_USERS = [76294506]
OWNER_QQ = 76294506
MAX_HISTORY = 50
MAX_TOKENS = 12000
MAX_OUTPUT = 1000
CONFIG_PATH = Path(__file__).parent / "config.json"
SESSION_PATH = Path(__file__).parent / "sessions.json"
FILE_SHARE_DIR = "/opt/napcat/data/share"

os.makedirs(FILE_SHARE_DIR, exist_ok=True)

BLOCKED_CMDS = [
    r"\brm\s+.*-r.*\s+/", r"\brm\s+-rf\s+", r"\brm\s+.*\s+/\*",
    r"\bmkfs\b", r"\bdd\s+if=", r"\bfdisk\b", r"\bparted\b",
    r"\breboot\b", r"\bshutdown\b", r"\bpoweroff\b", r"\bhalt\b", r"\binit\s+[06]",
    r">\s*/dev/sd", r">\s*/dev/null.*<", r"/etc/shadow", r"/etc/passwd",
    r":\(\)\s*\{", r"\.:\s*\|",
    r"\bkill\s+-9\s+1\b", r"\bkillall\s+-9",
    r"\biptables\s+-F", r"\biptables\s+.*DROP",
]

def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def load_sessions():
    try:
        with open(SESSION_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            for uid, s in data.items():
                s["history"] = deque(s.get("history", []), maxlen=MAX_HISTORY)
            return data
    except:
        return {}

def save_sessions():
    try:
        data = {}
        for uid, s in sessions.items():
            data[str(uid)] = {
                "history": list(s["history"]),
                "summary": s.get("summary", ""),
                "count": s.get("count", 0),
                "last_active": datetime.now().isoformat()
            }
        with open(SESSION_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存会话失败: {e}")

CONFIG = load_config()
sessions = load_sessions()
group_cache = {}
llm_semaphore = asyncio.Semaphore(5)

def get_session(uid):
    uid = str(uid)
    if uid not in sessions:
        sessions[uid] = {"history": deque(maxlen=MAX_HISTORY), "summary": "", "count": 0}
    return sessions[uid]

async def refresh_groups():
    global group_cache
    try:
        async with aiohttp.ClientSession() as http:
            async with http.get(f"{NAPCAT_HTTP}/get_group_list", timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = await r.json()
                    groups = data.get("data", [])
                    group_cache = {g["group_name"]: g["group_id"] for g in groups}
                    return group_cache
    except:
        pass
    return group_cache

async def send_group_msg(group_id, msg, at_qq=None):
    if at_qq:
        msg = f"[CQ:at,qq={at_qq}] {msg}"
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(f"{NAPCAT_HTTP}/send_group_msg",
                json={"group_id": group_id, "message": msg},
                timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    return (await r.json()).get("retcode") == 0
    except:
        pass
    return False

async def find_group(name):
    if not group_cache:
        await refresh_groups()
    if name in group_cache:
        return group_cache[name]
    for gname, gid in group_cache.items():
        if name in gname or gname in name:
            return gid
    return None

def is_cmd_safe(cmd):
    for pattern in BLOCKED_CMDS:
        if re.search(pattern, cmd.strip(), re.IGNORECASE):
            return False
    return True

def run_bash(cmd, timeout=30):
    if not is_cmd_safe(cmd):
        return "命令被安全策略阻止"
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        output = result.stdout + result.stderr
        lines = [l for l in output.split("\n") if "overlay" not in l]
        output = "\n".join(lines)
        if len(output) > MAX_OUTPUT:
            output = output[:MAX_OUTPUT] + "\n...(截断)"
        return output.strip() or "(无输出)"
    except subprocess.TimeoutExpired:
        return "命令超时"
    except Exception as e:
        return f"错误: {e}"

def extract_commands(text):
    """提取命令，兼容多种LLM输出格式"""
    cmds = []
    # <bash>cmd</bash>
    cmds += re.findall(r"<bash>(.*?)</bash>", text, re.DOTALL)
    # ```bash\ncmd\n``` or ```shell\ncmd\n```
    if not cmds:
        cmds += re.findall(r"```(?:bash|shell|sh)\s*\n(.*?)```", text, re.DOTALL)
    # /bash\ncmd (GLM style)
    if not cmds:
        cmds += re.findall(r"/bash\s*\n(.*?)(?:\n\n|$)", text, re.DOTALL)
    return [c.strip() for c in cmds if c.strip()]

def strip_command_tags(text):
    """从回复中去除命令标签，只保留说明文字"""
    text = re.sub(r"<bash>.*?</bash>", "", text, flags=re.DOTALL)
    text = re.sub(r"```(?:bash|shell|sh)\s*\n.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"/bash\s*\n.*?(?:\n\n|$)", "", text, flags=re.DOTALL)
    text = re.sub(r"<send_file>.*?</send_file>", "", text, flags=re.DOTALL)
    return text.strip()

def run_commands(cmds):
    results = []
    for cmd in cmds:
        results.append(f"$ {cmd}\n{run_bash(cmd)}")
    return results

async def send_qq(uid, msg):
    async with aiohttp.ClientSession() as http:
        if len(msg) <= 2000:
            await http.post(f"{NAPCAT_HTTP}/send_private_msg", json={"user_id": int(uid), "message": msg})
        else:
            for i in range(0, len(msg), 2000):
                await http.post(f"{NAPCAT_HTTP}/send_private_msg", json={"user_id": int(uid), "message": msg[i:i+2000]})
                if i + 2000 < len(msg): await asyncio.sleep(0.5)

async def send_file(uid, file_path, filename=None):
    if not os.path.exists(file_path):
        return False, "文件不存在"
    if not filename:
        filename = os.path.basename(file_path)
    share_path = os.path.join(FILE_SHARE_DIR, filename)
    try:
        shutil.copy2(file_path, share_path)
        os.chmod(share_path, 0o644)
    except Exception as e:
        return False, f"复制失败: {e}"

    container_path = f"/app/napcat/config/share/{filename}"
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(f"{NAPCAT_HTTP}/upload_private_file",
                json={"user_id": int(uid), "file": container_path, "name": filename},
                timeout=aiohttp.ClientTimeout(total=60)) as r:
                data = await r.json()
                return data.get("retcode") == 0, data.get("message", "")
    except Exception as e:
        return False, str(e)

def build_system_prompt(session_info=""):
    info = CONFIG.get("server_info", {})
    skills = CONFIG.get("skills", {})
    sw = info.get("software", {})

    prompt = f"""你是「小芳助手」，主人的私人AI助手，拥有服务器完全控制权限。

## 核心原则
1. **主动解决问题** - 遇到问题自己解决，不要问"你要哪个方案"
2. **保持连续性** - 你有持久记忆，会话不会丢失，放心工作
3. **一步到位** - 安装依赖一次装全，不要分步试探

## 当前会话状态
{session_info}

## 文件发送
用 <send_file>/path/to/file</send_file> 直接发送文件给主人

## 服务器信息
- IP: {info.get("ip", "101.35.227.232")} | 系统: {info.get("os", "Ubuntu 22.04")}
- 配置: {info.get("cpu", "4核")} / {info.get("memory", "3.3GB")}内存
- 软件: Docker, Java {sw.get("java", "17")}, Python {sw.get("python", "3.10")}, Node 20.19
- 服务: Clash(VPN), Antigravity(AI代理), NapCat(QQ框架)

## 执行命令
用 <bash>命令</bash> 执行

## 快捷技能
"""
    for skill, data in skills.items():
        prompt += f"- {skill}: {data.get('desc', '')}\n"

    prompt += """
## 行为准则
- 自己解决问题，不要问
- 简洁回复，3-5行
- 发现问题主动说
- 完成任务直接告诉结果
"""
    return prompt

async def compress_history(session):
    if not session["history"]:
        return 0
    history_count = len(session["history"])
    text = "\n".join([f"{m['role']}: {m['content']}" for m in session["history"]])

    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(f"{LLM_API}/v1/messages",
                headers={"x-api-key": LLM_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": LLM_MODEL, "max_tokens": 800,
                      "messages": [{"role": "user", "content": f"压缩以下对话为详细摘要，保留：所有关键信息、待办事项、重要上下文、用户偏好。这个摘要将用于延续对话：\n\n{text}"}]},
                timeout=aiohttp.ClientTimeout(total=30)) as r:
                if r.status == 200:
                    session["summary"] = (await r.json())["content"][0]["text"]
                    session["history"].clear()
                    save_sessions()
                    return history_count
    except Exception as e:
        print(f"压缩错误: {e}")
    return 0

async def chat(uid, msg, is_group=False, group_id=None):
    uid = str(uid)
    s = get_session(uid)
    s["count"] += 1

    current_len = len("".join([m["content"] for m in s["history"]])) + len(msg)
    history_count = len(s["history"])

    session_info = f"历史消息: {history_count}条 | 已用约{current_len}字符 | 上限{MAX_TOKENS}字符"
    if s["summary"]:
        session_info += " | 有之前的摘要"

    need_compress = current_len > MAX_TOKENS * 0.8

    if is_group:
        system = """你是「小芳」，Java之家群里的技术人。
性格直爽，像朋友聊天，可以开玩笑。
不说自己是AI，不用"您"，不写长篇大论。"""
    else:
        system = build_system_prompt(session_info)

    if need_compress and not is_group:
        await send_qq(uid, f"上下文快满了({history_count}条/{current_len}字符)，压缩中...")
        compressed = await compress_history(s)
        if compressed > 0:
            await send_qq(uid, f"已压缩{compressed}条消息为摘要，继续工作~")
        else:
            await send_qq(uid, "压缩失败，清空历史")
            s["history"].clear()
            s["summary"] = ""

    if s["summary"]:
        system += f"\n\n## 之前对话的摘要（重要，请基于此继续）\n{s['summary']}"

    if need_compress and not is_group:
        messages = [{"role": "user", "content": msg}]
    else:
        messages = list(s["history"]) + [{"role": "user", "content": msg}]

    s["history"].append({"role": "user", "content": msg})

    max_rounds = 5
    try:
        async with llm_semaphore:
            for round_i in range(max_rounds):
                async with aiohttp.ClientSession() as http:
                    async with http.post(f"{LLM_API}/v1/messages",
                        headers={"x-api-key": LLM_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                        json={"model": LLM_MODEL, "max_tokens": 800 if is_group else 2000, "system": system, "messages": messages},
                        timeout=aiohttp.ClientTimeout(total=120)) as r:
                        if r.status != 200:
                            return f"API错误: {r.status}"
                        reply = (await r.json())["content"][0]["text"]

                if is_group:
                    break

                # 提取命令和文件
                cmds = extract_commands(reply)
                file_matches = re.findall(r"<send_file>(.*?)</send_file>", reply, re.DOTALL)

                if not cmds and not file_matches:
                    break

                # 发送中间状态（去掉命令标签的说明文字）
                desc = strip_command_tags(reply)
                if desc:
                    await send_qq(uid, desc)

                # 执行命令
                all_results = []
                if cmds:
                    all_results += run_commands(cmds)
                for fp in file_matches:
                    success, msg_r = await send_file(uid, fp.strip())
                    all_results.append(f"文件 {os.path.basename(fp)}: {'OK' if success else msg_r}")

                results_text = "\n".join(all_results)

                # 将结果回传 LLM 继续分析
                messages.append({"role": "assistant", "content": reply})
                messages.append({"role": "user", "content": f"[命令执行结果]\n{results_text}\n\n请分析结果，如需继续操作可继续执行命令，否则给出最终总结。"})

            s["history"].append({"role": "assistant", "content": reply})
            save_sessions()
            return reply
    except asyncio.TimeoutError: return "请求超时"
    except Exception as e: return f"出错了: {e}"

async def handle_skill(uid, skill_name, arg=""):
    skills = CONFIG.get("skills", {})
    aliases = {"/res": "/资源", "/容器": "/docker", "/svc": "/服务", "/net": "/网络", "/sec": "/安全"}
    skill_name = aliases.get(skill_name, skill_name)

    if skill_name in ["/help", "/帮助"]:
        return "可用技能:\n" + "\n".join([f"  {n} - {d.get('desc','')}" for n,d in skills.items()])

    if skill_name in skills:
        cmd = skills[skill_name].get("cmd", "")
        if "{arg}" in cmd:
            if arg: cmd = cmd.replace("{arg}", arg)
            else: return f"用法: {skill_name} <参数>"
        return run_bash(cmd)
    return None

async def handle(data):
    if data.get("post_type") != "message":
        return

    message_type = data.get("message_type")
    uid = data.get("user_id")
    msg = data.get("raw_message", "").strip()

    if message_type == "group":
        group_id = data.get("group_id")
        if f"[CQ:at,qq={data.get('self_id')}]" not in data.get("message", ""):
            return
        msg = re.sub(r'\[CQ:at,qq=\d+\]', '', msg).strip()
        if not msg: return
        print(f"[群聊] {group_id} - {uid}: {msg}")
        reply = await chat(f"group_{group_id}", msg, is_group=True, group_id=group_id)
        await send_group_msg(group_id, reply, at_qq=uid)
        return

    if message_type != "private" or uid not in ALLOWED_USERS or not msg:
        return
    print(f"[收到] {uid}: {msg}")

    if msg in ["/clear", "清空", "重置"]:
        sessions.pop(str(uid), None)
        save_sessions()
        await send_qq(uid, "对话已重置，会话清空")
        return

    if msg in ["/status", "状态"]:
        s = get_session(uid)
        history_len = len("".join([m["content"] for m in s["history"]]))
        await send_qq(uid, f"会话状态:\n消息数:{s['count']}\n历史:{len(s['history'])}条/{history_len}字符\n摘要:{'有' if s['summary'] else '无'}\n上限:{MAX_TOKENS}字符\nAPI: {LLM_API}\n模型: {LLM_MODEL}")
        return

    if msg.startswith("!"):
        await send_qq(uid, f"$ {msg[1:]}\n{run_bash(msg[1:])}")
        return

    if msg.startswith("/群发 ") or msg.startswith("/at "):
        at_me = msg.startswith("/at ")
        parts = msg.split(" ", 2)
        if len(parts) < 3:
            await send_qq(uid, "用法: /群发 群名 消息")
            return
        group_id = await find_group(parts[1])
        if not group_id:
            await send_qq(uid, f"找不到群「{parts[1]}」")
            return
        await send_group_msg(group_id, parts[2], OWNER_QQ if at_me else None)
        await send_qq(uid, f"已发送到 {parts[1]}")
        return

    if msg in ["/群列表", "/groups"]:
        groups = await refresh_groups()
        if groups:
            await send_qq(uid, "群列表:\n" + "\n".join(list(groups.keys())[:15]))
        return

    if msg.startswith("/"):
        parts = msg.split(maxsplit=1)
        result = await handle_skill(uid, parts[0], parts[1] if len(parts) > 1 else "")
        if result:
            await send_qq(uid, result)
            return

    reply = await chat(uid, msg)
    await send_qq(uid, reply)
    print(f"[回复] {reply[:80]}...")

async def main():
    print(f"小芳助手 v8 启动 ({LLM_MODEL} @ {LLM_API})")
    print(f"会话文件: {SESSION_PATH}")
    print(f"已加载 {len(sessions)} 个会话")
    if not LLM_KEY:
        print("警告: LLM_API_KEY 未设置!")
    while True:
        try:
            async with aiohttp.ClientSession() as http:
                async with http.ws_connect(NAPCAT_WS) as ws:
                    print("WebSocket已连接")
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try: await handle(json.loads(msg.data))
                            except Exception as e: print(f"处理错误: {e}")
        except Exception as e:
            print(f"连接断开: {e}, 5秒后重连...")
            await asyncio.sleep(5)

if __name__ == "__main__": asyncio.run(main())
