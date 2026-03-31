@echo off
REM 后台启动 Hub 服务
cd C:\agent-hub
start /B python -m uvicorn hub_server.main:app --host 0.0.0.0 --port 8000
echo Hub service started in background
