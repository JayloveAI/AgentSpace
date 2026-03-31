@echo off
chcp 65001 > nul
echo ====================================================
echo   FRP Client + Agent Test
echo ====================================================
echo.

echo [1/3] Starting FRP Client...
start /B E:\frp\frpc.exe -c E:\frp\frpc.ini

echo [2/3] Waiting for FRP connection...
timeout /t 3 /nobreak > nul

echo [3/3] Running Agent Test...
echo.
cd E:\agent-hub
python test_two_agents_frp.py

pause
