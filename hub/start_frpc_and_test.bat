@echo off
echo ====================================================
echo   FRP Client + Agent Test - 一键启动
echo ====================================================
echo.

REM 启动 FRP 客户端（后台运行）
echo [1/3] 启动 FRP 客户端...
start /B E:\frp\frpc.exe -c E:\frp\frpc.ini

REM 等待 FRP 连接
echo [2/3] 等待 FRP 连接...
timeout /t 3 /nobreak > nul

REM 运行测试
echo [3/3] 运行双 Agent 测试...
echo.
cd E:\agent-hub
python test_two_agents_frp.py

pause
