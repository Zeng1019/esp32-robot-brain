#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小栗桥接 MCP Server（stdio）。

注册进 ~/.workbuddy/mcp.json 后，WorkBuddy 会话即可用 MCP 协议接语音任务：
  · get_agent_task(wait_seconds)           长轮询取一条语音任务（无单返回 none）
  · finish_agent_task(task_id, summary, success)  回传结果，桥接推给小栗播报

与 bridge_server.py 通过 127.0.0.1:8787 通信，凭据读 config.yaml 的
security.device_token。实现为最小 MCP stdio（JSON-RPC 2.0），零第三方依赖。
"""
import json
import os
import re
import sys
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BRIDGE = "http://127.0.0.1:8787"

try:  # Windows 下 stdio 默认可能是 GBK，MCP 报文一律 UTF-8
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _token():
    try:
        with open(os.path.join(BASE_DIR, "config.yaml"), encoding="utf-8") as f:
            m = re.search(r'device_token:\s*"([^"]+)"', f.read())
        return m.group(1) if m else ""
    except Exception:
        return ""


_TOKEN = _token()


def _http(method, path, payload=None, timeout=75):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(BRIDGE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if _TOKEN:
        req.add_header("X-Device-Token", _TOKEN)
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 本机直连，绕系统代理
    with op.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def tool_get_agent_task(wait_seconds: int = 45):
    wait_seconds = max(1, min(int(wait_seconds), 60))
    r = _http("GET", f"/agent_task/poll?wait={wait_seconds}")
    t = r.get("task")
    if not t:
        return {"status": "none", "hint": "当前没有待接的语音任务。"}
    return {"status": "task", "task_id": t["id"], "text": t["text"],
            "hint": "立即执行该任务；完成后必须调用 finish_agent_task(task_id, "
                    "summary) 回传结果。summary 是念给用户听的一句话（≤80字，"
                    "口语化，说结果不说过程）。"}


def tool_finish_agent_task(task_id: int, summary: str, success: bool = True):
    return _http("POST", "/agent_task/finish",
                 {"task_id": int(task_id), "summary": str(summary),
                  "success": bool(success)})


TOOLS = [
    {
        "name": "get_agent_task",
        "description": "从小栗桌面机器人桥接服务取一条待执行的语音任务（长轮询，"
                       "最多等 wait_seconds 秒）。返回 status=none 表示暂无任务；"
                       "返回 task 时须立即执行任务文本，完成后调用 finish_agent_task。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "wait_seconds": {"type": "integer",
                                 "description": "长轮询等待秒数，默认 45，上限 60"}
            },
        },
    },
    {
        "name": "finish_agent_task",
        "description": "回传语音任务的执行结果。summary 会被小栗机器人直接语音"
                       "播报给主人，请用一句口语化的短句（≤80字）讲结果。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "get_agent_task 返回的任务 id"},
                "summary": {"type": "string", "description": "给用户听的播报文本（≤80字）"},
                "success": {"type": "boolean", "description": "是否执行成功，默认 true"},
            },
            "required": ["task_id", "summary"],
        },
    },
]


def _reply(msg_id, result=None, error=None):
    resp = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        resp["error"] = error
    else:
        resp["result"] = result
    sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _dispatch(name, args):
    if name == "get_agent_task":
        return tool_get_agent_task(**(args or {}))
    if name == "finish_agent_task":
        return tool_finish_agent_task(**(args or {}))
    raise KeyError(name)


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        method = msg.get("method")
        mid = msg.get("id")
        if method == "initialize":
            _reply(mid, {
                "protocolVersion": (msg.get("params") or {}).get(
                    "protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "xiaoli-bridge", "version": "1.1.0"},
            })
        elif method == "notifications/initialized":
            continue  # 通知无需应答
        elif method == "ping":
            _reply(mid, {})
        elif method == "tools/list":
            _reply(mid, {"tools": TOOLS})
        elif method == "tools/call":
            params = msg.get("params") or {}
            name = params.get("name", "")
            try:
                out = _dispatch(name, params.get("arguments") or {})
                _reply(mid, {"content": [
                    {"type": "text", "text": json.dumps(out, ensure_ascii=False)}]})
            except KeyError:
                _reply(mid, error={"code": -32602, "message": f"unknown tool: {name}"})
            except Exception as e:  # noqa: BLE001
                _reply(mid, {"content": [
                    {"type": "text", "text": json.dumps(
                        {"error": str(e)}, ensure_ascii=False)}],
                    "isError": True})
        elif mid is not None:
            _reply(mid, error={"code": -32601, "message": f"unknown method: {method}"})


if __name__ == "__main__":
    main()
