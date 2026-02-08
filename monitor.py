#!/usr/bin/env python3
"""
服务器主动监控脚本 (QQ告警, 24h同类冷却)
"""
import subprocess, requests, json, time
from datetime import datetime
from pathlib import Path

NAPCAT_HTTP = "http://127.0.0.1:3000"
OWNER_QQ = 76294506
STATE_DIR = Path("/var/lib/ha-monitor")
COOLDOWN = 86400  # 24h

STATE_DIR.mkdir(parents=True, exist_ok=True)

def run_cmd(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return r.stdout + r.stderr
    except:
        return ""

def should_alert(alert_type):
    f = STATE_DIR / f"mon_{alert_type}"
    try:
        last = int(f.read_text().strip())
    except:
        last = 0
    now = int(time.time())
    if now - last < COOLDOWN:
        return False
    f.write_text(str(now))
    return True

def send_qq(msg):
    try:
        requests.post(f"{NAPCAT_HTTP}/send_private_msg",
                     json={"user_id": OWNER_QQ, "message": msg}, timeout=10)
    except:
        pass

def check_server():
    alerts = []

    mem = run_cmd("free | awk '/Mem:/{printf \"%.0f\", $3/$2*100}'")
    try:
        if int(mem.strip()) > 90 and should_alert("mem"):
            alerts.append(f"内存告警: {mem.strip()}%")
    except: pass

    disk = run_cmd("df / | awk 'NR==2{gsub(/%/,\"\"); print $5}'")
    try:
        if int(disk.strip()) > 85 and should_alert("disk"):
            alerts.append(f"磁盘告警: {disk.strip()}%")
    except: pass

    load = run_cmd("cat /proc/loadavg | awk '{print $1}'")
    try:
        if float(load.strip()) > 4.0 and should_alert("cpu"):
            alerts.append(f"CPU负载告警: {load.strip()}")
    except: pass

    services = {"clash": "VPN代理", "docker": "Docker", "qq-claude-bot": "QQ Bot"}
    for svc, name in services.items():
        status = run_cmd(f"systemctl is-active {svc} 2>/dev/null").strip()
        if status != "active" and should_alert(f"svc_{svc}"):
            alerts.append(f"服务异常: {name} ({status})")

    containers = ["napcat", "antigravity-manager"]
    running = run_cmd("docker ps --format '{{.Names}}'").strip().split("\n")
    for c in containers:
        if c not in running and should_alert(f"ctn_{c}"):
            alerts.append(f"容器异常: {c}")

    return alerts

def main():
    now = datetime.now().strftime("%m-%d %H:%M")
    alerts = check_server()
    if alerts:
        msg = f"[服务器告警] {now}\n" + "\n".join(alerts) + "\n\n回复 /资源 查看详情"
        send_qq(msg)
        print(f"[{now}] 告警: {len(alerts)}条")
    else:
        print(f"[{now}] 正常")

if __name__ == "__main__":
    main()
