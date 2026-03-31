# Agent Hub Windows 部署脚本
# 使用方法: powershell -ExecutionPolicy Bypass -File deploy_windows.ps1

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  Agent Universal Hub 部署向导" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# 检查管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[错误] 请以管理员身份运行此脚本" -ForegroundColor Red
    exit 1
}

# 创建目录
$hubPath = "C:\agent-hub"
$backupPath = "C:\agent-hub\backups"
$logPath = "C:\agent-hub\logs"

Write-Host "[1/6] 创建目录结构..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $hubPath | Out-Null
New-Item -ItemType Directory -Force -Path $backupPath | Out-Null
New-Item -ItemType Directory -Force -Path $logPath | Out-Null

# 检查 Python
Write-Host "[2/6] 检查 Python 环境..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  Python 已安装: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  Python 未安装" -ForegroundColor Red
    Write-Host "  请访问 https://www.python.org/downloads/ 安装 Python 3.10+" -ForegroundColor Yellow
    pause
    exit 1
}

# 检查 PostgreSQL
Write-Host "[3/6] 检查 PostgreSQL..." -ForegroundColor Yellow
try {
    $pgVersion = psql --version 2>&1
    Write-Host "  PostgreSQL 已安装: $pgVersion" -ForegroundColor Green
} catch {
    Write-Host "  PostgreSQL 未安装" -ForegroundColor Red
    Write-Host "  请访问 https://www.postgresql.org/download/windows/ 安装 PostgreSQL 15" -ForegroundColor Yellow
    Write-Host "  安装后需要安装 pgvector 扩展" -ForegroundColor Yellow
    pause
    exit 1
}

# 安装 Python 依赖
Write-Host "[4/6] 安装 Python 依赖..." -ForegroundColor Yellow
$requirements = @"
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3
pydantic-settings==2.1.0
python-dotenv==1.0.0
python-jose[cryptography]==3.3.0
httpx==0.26.0
psycopg2-binary==2.9.9
"@

$requirements | Out-File -FilePath "$hubPath\requirements.txt" -Encoding UTF8
pip install -r "$hubPath\requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple

# 创建 .env 配置
Write-Host "[5/6] 配置环境变量..." -ForegroundColor Yellow
Write-Host "  请输入数据库配置:" -ForegroundColor Cyan
$dbUser = Read-Host "  数据库用户名 (默认: postgres)"
if (-not $dbUser) { $dbUser = "postgres" }

$dbPass = Read-Host "  数据库密码"
$dbHost = Read-Host "  数据库主机 (默认: localhost)"
if (-not $dbHost) { $dbHost = "localhost" }

$dbPort = Read-Host "  数据库端口 (默认: 5432)"
if (-not $dbPort) { $dbPort = "5432" }

$dbName = Read-Host "  数据库名称 (默认: agent_hub)"
if (-not $dbName) { $dbName = "agent_hub" }

Write-Host "  请输入 Embedding API 配置:" -ForegroundColor Cyan
Write-Host "  1. GLM (智谱)" -ForegroundColor Cyan
Write-Host "  2. OpenAI" -ForegroundColor Cyan
$choice = Read-Host "  选择 Embedding 提供商 (1/2, 默认: 1)"
if (-not $choice) { $choice = "1" }

if ($choice -eq "1") {
    $provider = "glm"
    $apiKey = Read-Host "  请输入 GLM API Key"
    $model = "embedding-2"
} else {
    $provider = "openai"
    $apiKey = Read-Host "  请输入 OpenAI API Key"
    $model = "text-embedding-ada-002"
}

$jwtSecret = Read-Host "  请输入 JWT Secret (留空自动生成)"
if (-not $jwtSecret) {
    $jwtSecret = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | % {[char]$_})
}

$envContent = @"
# Agent Hub Configuration
DATABASE_URL=postgresql://${dbUser}:${dbPass}@${dbHost}:${dbPort}/${dbName}
EMBEDDING_PROVIDER=${provider}
$("$($provider.ToUpper())_API_KEY")=$apiKey
$("$($provider.ToUpper())_EMBEDDING_MODEL")=$model
HUB_JWT_SECRET=$jwtSecret
"@

$envContent | Out-File -FilePath "$hubPath\.env" -Encoding UTF8
Write-Host "  配置已保存到 $hubPath\.env" -ForegroundColor Green

# 创建启动脚本
Write-Host "[6/6] 创建启动脚本..." -ForegroundColor Yellow

$startScript = @'
@echo off
chcp 65001 >nul
title Agent Universal Hub Server
cd /d C:\agent-hub
echo Starting Agent Universal Hub Server...
echo API URL: http://0.0.0.0:8000
echo API Docs: http://localhost:8000/docs
echo.
python -m uvicorn hub_server.main:app --host 0.0.0.0 --port 8000 --reload
pause
'@

$startScript | Out-File -FilePath "$hubPath\start.bat" -Encoding Default

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "  部署准备完成！" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "下一步操作:" -ForegroundColor Cyan
Write-Host "  1. 将项目文件复制到 C:\agent-hub" -ForegroundColor White
Write-Host "  2. 确保数据库已创建并安装 pgvector 扩展" -ForegroundColor White
Write-Host "  3. 运行 C:\agent-hub\start.bat 启动服务" -ForegroundColor White
Write-Host ""
Write-Host "数据库初始化 SQL:" -ForegroundColor Yellow
Write-Host "  CREATE DATABASE agent_hub;" -ForegroundColor White
Write-Host "  \c agent_hub" -ForegroundColor White
Write-Host "  CREATE EXTENSION vector;" -ForegroundColor White
Write-Host ""
Write-Host "服务启动后访问: http://your-server-ip:8000/docs" -ForegroundColor Green
Write-Host ""
pause
