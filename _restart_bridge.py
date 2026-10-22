# -*- coding: utf-8 -*-
"""重启桥接服务（一键工具）：
1. 用 PowerShell CIM 找到运行中的 bridge_server.py 进程并杀掉；
2. 用分离进程方式拉起 .venv 的 pythonw（比 vbs 路径更可靠，cwd 固定）；
3. 探测 8787 端口确认存活。
用法：任意 python 3.x  _restart_bridge.py
"""
import os
import socket
import subprocess
import time

ROOT = r"E:\esp32\esp32-robot-brain"
PYW = os.path.join(ROOT, ".venv", "Scripts", "pythonw.exe")
MAIN = os.path.join(ROOT, "bridge_server.py")
DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

ps = ("Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
      "Where-Object { $_.CommandLine -like '*bridge_server.py*' } | "
      "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false }")
r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   capture_output=True, text=True, timeout=30)
print("kill rc:", r.returncode)
time.sleep(2)

# 用 WMI Win32_Process.Create 拉起：创建的进程挂在 WMI 服务下，
# 不随本脚本/会话退出被回收（Popen DETACHED 实测会被会话清理杀掉，
# 2026-10-11 18:03 与 17:2x 两次"桥接莫名死亡"皆因此）。
cmdline = '"%s" "%s"' % (PYW, MAIN)
ps_launch = ('$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create '
             "-Arguments @{ CommandLine = '%s'; CurrentDirectory = '%s' }; "
             'Write-Output ("rc=" + $r.ReturnValue + " pid=" + $r.ProcessId)'
             % (cmdline.replace("'", "''"), ROOT))
r = subprocess.run(["powershell", "-NoProfile", "-Command", ps_launch],
                   capture_output=True, text=True, timeout=30)
print("launch:", (r.stdout or r.stderr).strip()[:120])
print("waiting for port ...")
ok = False
for _ in range(30):  # 最多等 30s（cv2 等重依赖导入较慢）
    time.sleep(1)
    s = socket.socket()
    s.settimeout(2)
    try:
        s.connect(("127.0.0.1", 8787))
        ok = True
    except OSError:
        ok = False
    finally:
        s.close()
    if ok:
        break
print("port 8787:", "OPEN" if ok else "仍拒绝连接（看 data/bridge.log）")
