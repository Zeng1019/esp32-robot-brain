# -*- coding: utf-8 -*-
"""小栗桥接看门狗（计划任务每分钟调用）：
探测 127.0.0.1:8787，不可达则调 _restart_bridge.py 拉起。
覆盖场景：开机自启失败 / 进程崩溃 / 休眠唤醒后异常 / 设备插拔影响。
日志：data/watchdog.log
"""
import os
import socket
import subprocess
import sys
import time

ROOT = r"E:\esp32\esp32-robot-brain"
LOG = os.path.join(ROOT, "data", "watchdog.log")
RESTART = os.path.join(ROOT, "_restart_bridge.py")


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg + "\n")
    except Exception:
        pass


def port_open():
    s = socket.socket()
    s.settimeout(2)
    try:
        s.connect(("127.0.0.1", 8787))
        return True
    except OSError:
        return False
    finally:
        s.close()


def main():
    if port_open():
        return  # 正常，安静退出（不写日志，避免刷屏）
    log("8787 不可达，执行自动重启")
    try:
        r = subprocess.run([sys.executable, RESTART],
                           capture_output=True, text=True, timeout=120)
        tail = ((r.stdout or "") + (r.stderr or "")).strip().replace("\n", " | ")
        log("restart rc=%s out=%s" % (r.returncode, tail[-200:]))
    except Exception as e:
        log("restart 异常: %r" % e)
    time.sleep(2)
    log("重启后端口: %s" % ("OPEN" if port_open() else "仍不可达"))


if __name__ == "__main__":
    main()
