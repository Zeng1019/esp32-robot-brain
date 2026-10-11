#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""语音任务看门：长轮询桥接 /agent_task/poll，取到任务立即打印并退出。

由 WorkBuddy 会话以后台任务方式运行——脚本一退出，会话 Agent 就会收到
后台任务完成通知并接单执行；执行完调 finish_agent_task（或直接 POST
/agent_task/finish）回传结果，桥接推给小栗播报。
桥接不可达时按 5s 退避静默重试；只有取到任务才会退出（exit 0）。
"""
import json
import os
import re
import sys
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BRIDGE = "http://127.0.0.1:8787"
POLL_WAIT = 55  # 单次长轮询秒数（桥接上限 60）


def _token():
    try:
        with open(os.path.join(BASE_DIR, "config.yaml"), encoding="utf-8") as f:
            m = re.search(r'device_token:\s*"([^"]+)"', f.read())
        return m.group(1) if m else ""
    except Exception:
        return ""


def main():
    token = _token()
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 绕系统代理
    backoff = 5
    while True:
        try:
            req = urllib.request.Request(f"{BRIDGE}/agent_task/poll?wait={POLL_WAIT}")
            if token:
                req.add_header("X-Device-Token", token)
            with op.open(req, timeout=POLL_WAIT + 15) as r:
                data = json.loads(r.read().decode("utf-8"))
            task = data.get("task")
            if task:
                sys.stdout.write(json.dumps(
                    {"kind": "voice_task", "task_id": task["id"],
                     "text": task["text"]}, ensure_ascii=False) + "\n")
                sys.stdout.flush()
                return 0  # 退出 → WorkBuddy 收到通知接单
            backoff = 5  # 桥接正常，继续轮
        except Exception:
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)


if __name__ == "__main__":
    sys.exit(main())
