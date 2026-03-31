@echo off
chcp 65001 >nul
echo ============================================
echo   AgentSpace V1.6 - One-Click Full Deploy
echo ============================================
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0deploy_all.ps1"
pause
