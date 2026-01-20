#!/usr/bin/env python3
"""
服务器主动监控脚本
定期检查服务器状态，异常时通过QQ通知主人
"""
import subprocess
import requests
import json
from datetime import datetime

NAPCAT_HTTP = "http://127.0.0.1:3000"
OWNER_QQ = 76294506

def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout + result.stderr
    except:
        return ""

def send_qq(msg):
    try:
        requests.post(f"{NAPCAT_HTTP}/send_private_msg",
                     json={"user_id": OWNER_QQ, "message": msg}, timeout=10)
    except:
        pass

def check_server():
    alerts = []

    # 1. 检查内存
    mem = run_cmd("free | awk '/Mem:/{printf \"%.0f\", $3/$2*100}'")
    try:
        mem_pct = int(mem.strip())
        if mem_pct > 90:
            alerts.append(f"内存告警: {mem_pct}%使用")
    except: pass

    # 2. 检查磁盘
    disk = run_cmd("df / | awk 'NR==2{gsub(/%/,\"\"); print $5}'")
    try:
        disk_pct = int(disk.strip())
        if disk_pct > 85:
            alerts.append(f"磁盘告警: {disk_pct}%使用")
    except: pass

    # 3. 检查CPU负载
    load = run_cmd("cat /proc/loadavg | awk '{print $1}'")
    try:
        load_val = float(load.strip())
        if load_val > 3.5:
            alerts.append(f"CPU负载告警: {load_val}")
    except: pass

    # 4. 检查关键服务
    services = {"clash": "VPN代理", "docker": "Docker", "qq-claude-bot": "QQ Bot"}
    for svc, name in services.items():
        status = run_cmd(f"systemctl is-active {svc} 2>/dev/null").strip()
        if status != "active":
            alerts.append(f"服务异常: {name} 状态={status}")

    # 5. 检查关键容器
    containers = ["napcat", "antigravity-manager"]
    docker_ps = run_cmd("docker ps --format '{{.Names}}'")
    running = docker_ps.strip().split("\n")
    for c in containers:
        if c not in running:
            alerts.append(f"容器异常: {c} 未运行")

    # 6. 检查僵尸进程
    zombie = run_cmd("ps aux | awk '$8==\"Z\"' | wc -l")
    try:
        zombie_count = int(zombie.strip())
        if zombie_count > 100:
            alerts.append(f"僵尸进程: {zombie_count}个")
    except: pass

    return alerts

def main():
    now = datetime.now().strftime("%m-%d %H:%M")
    alerts = check_server()

    if alerts:
        msg = f"[服务器告警] {now}\n"
        msg += "\n".join(alerts)
        msg += "\n\n回复 /资源 查看详情"
        send_qq(msg)
        print(f"[{now}] 告警: {len(alerts)}条")
    else:
        print(f"[{now}] 正常")

if __name__ == "__main__":
    main()
