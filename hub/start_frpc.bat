@echo off
echo ====================================================
echo   FRP Client - 启动脚本
echo ====================================================
echo.
echo 连接到云服务器: your-server-ip:7000
echo.

cd E:\frp
frpc -c frpc.ini

pause
