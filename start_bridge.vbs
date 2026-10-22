' 小栗桥接服务启动器（任务计划程序/开机自启用，无窗口后台运行）
Set ws = CreateObject("WScript.Shell")
ws.Run """E:\esp32\esp32-robot-brain\.venv\Scripts\pythonw.exe"" ""E:\esp32\esp32-robot-brain\bridge_server.py""", 0, False
