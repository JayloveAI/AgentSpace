@echo off
REM Agent Universal Hub 快速启动脚本 (Windows)

echo 🚀 Agent Universal Hub - 快速启动
echo ==================================
echo.

REM 检查 Docker
docker --version >/dev/null 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未安装 Docker
    echo    请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

REM 复制环境变量模板
if not exist .env (
    echo 📄 创建 .env 文件...
    copy .env.example .env
    echo ⚠️  请编辑 .env 文件，设置你的 OpenAI API Key
    echo.
)

REM 启动服务
echo 🐳 启动 Docker 服务...
docker-compose up -d

echo.
echo ✅ 服务已启动！
echo.
echo 📍 访问地址:
echo    - Hub API:     http://localhost:8000
echo    - API 文档:    http://localhost:8000/docs
echo    - PostgreSQL:  localhost:5432
echo.
echo 📊 查看日志: docker-compose logs -f
echo 🛑 停止服务: docker-compose down
echo.
pause
