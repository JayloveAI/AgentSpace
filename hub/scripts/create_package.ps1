# Agent Hub 部署包打包脚本
# 将项目文件打包，方便上传到腾讯云服务器

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  Agent Hub 部署包打包工具" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

$projectRoot = "e:\hub"
$packageDir = "$projectRoot\package"
$zipFile = "$projectRoot\agent_hub_deploy.zip"

# 清理旧的打包文件
Write-Host "[1/5] 清理旧文件..." -ForegroundColor Yellow
if (Test-Path $packageDir) {
    Remove-Item $packageDir -Recurse -Force
}
if (Test-Path $zipFile) {
    Remove-Item $zipFile -Force
}

# 创建打包目录结构
Write-Host "[2/5] 创建打包目录..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$packageDir\hub_server" | Out-Null
New-Item -ItemType Directory -Force -Path "$packageDir\scripts" | Out-Null
New-Item -ItemType Directory -Force -Path "$packageDir\logs" | Out-Null

# 复制必要文件
Write-Host "[3/5] 复制项目文件..." -ForegroundColor Yellow

# Hub 服务端
Copy-Item -Path "$projectRoot\hub_server\*" -Destination "$packageDir\hub_server\" -Recurse -Force

# 配置文件
Copy-Item -Path "$projectRoot\.env" -Destination "$packageDir\" -Force -ErrorAction SilentlyContinue
Copy-Item -Path "$projectRoot\requirements.txt" -Destination "$packageDir\" -Force -ErrorAction SilentlyContinue

# 脚本文件
Copy-Item -Path "$projectRoot\scripts\*.ps1" -Destination "$packageDir\scripts\" -Force
Copy-Item -Path "$projectRoot\scripts\*.sql" -Destination "$packageDir\scripts\" -Force

# 文档
Copy-Item -Path "$projectRoot\*.md" -Destination "$packageDir\" -Force

# 创建 .env 模板
Write-Host "[4/5] 创建配置模板..." -ForegroundColor Yellow
$envTemplate = @"
# Agent Universal Hub Configuration
# 腾讯云部署配置

# 数据库配置
DATABASE_URL=postgresql://postgres:YOUR_DB_PASSWORD@localhost:5432/agent_hub

# Embedding API 配置
EMBEDDING_PROVIDER=glm
GLM_API_KEY=a6fd75f395f545a1972483cf8fd46549.jmTm8fXJ5X6Oyaec
GLM_EMBEDDING_MODEL=embedding-2

# JWT 密钥
HUB_JWT_SECRET=change-me-in-production

# 服务配置
HUB_HOST=0.0.0.0
HUB_PORT=8000
"@
$envTemplate | Out-File -FilePath "$packageDir\.env.template" -Encoding UTF8

# 创建快速部署说明
Write-Host "[5/5] 创建部署说明..." -ForegroundColor Yellow
$readme = @"
# Agent Universal Hub - 腾讯云部署包

## 服务器信息

- 公网IP: your-server-ip
- 实例ID: lhins-10zmw6w0
- 系统: Windows Server + 宝塔面板

## 快速部署步骤

### 1. 上传部署包

将本压缩包上传到服务器 C:\ 目录并解压。

### 2. 安装 Python

下载并安装 Python 3.10+:
https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe

安装时勾选 "Add Python to PATH"

### 3. 安装 PostgreSQL

下载并安装 PostgreSQL 15:
https://get.enterprisedb.com/postgresql/postgresql-15.2-1-windows-x64.exe

记住设置的 postgres 密码。

### 4. 安装 pgvector 扩展

下载 pgvector:
https://github.com/pgvector/pgvector/releases

将 pgvector.dll 复制到: C:\Program Files\PostgreSQL\15\lib\
将 pgvector.control 复制到: C:\Program Files\PostgreSQL\15\share\extension\

### 5. 初始化数据库

```powershell
cd C:\package
psql -U postgres -f scripts\init_db.sql
```

### 6. 配置环境变量

```powershell
cd C:\package
copy .env.template .env
notepad .env
```

修改数据库密码为实际值。

### 7. 安装依赖

```powershell
cd C:\package
pip install -r requirements.txt
```

### 8. 安装为系统服务

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_service.ps1
```

### 9. 验证部署

浏览器访问: http://your-server-ip:8000/docs

## 服务管理

```powershell
# 启动服务
nssm start AgentHub

# 停止服务
nssm stop AgentHub

# 重启服务
nssm restart AgentHub

# 查看状态
nssm status AgentHub
```

## 防火墙配置

在腾讯云控制台添加安全组规则:
- 端口 8000 (HTTP)
- 端口 8888 (宝塔面板)

## 客户端连接配置

```python
from agent_hub_client import HubConnector

agent = HubConnector(
    agent_id="my_agent",
    local_port=8000,
    hub_url="http://your-server-ip:8000"
)
```

## 问题排查

### 查看服务日志
```powershell
nssm edit AgentHub
```

### 查看防火墙状态
```powershell
netsh advfirewall show allprofiles
```

### 检查端口占用
```powershell
netstat -ano | findstr :8000
```
"@
$readme | Out-File -FilePath "$packageDir\DEPLOY_README.txt" -Encoding UTF8

# 创建 ZIP 压缩包
Write-Host ""
Write-Host "创建压缩包..." -ForegroundColor Yellow
Compress-Archive -Path "$packageDir\*" -DestinationPath $zipFile -Force

# 获取文件大小
$fileSize = (Get-Item $zipFile).Length / 1MB

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "  打包完成！" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "部署包位置:" -ForegroundColor Cyan
Write-Host "  $zipFile" -ForegroundColor White
Write-Host ""
Write-Host "文件大小:" -ForegroundColor Cyan
Write-Host "  $([math]::Round($fileSize, 2)) MB" -ForegroundColor White
Write-Host ""
Write-Host "下一步:" -ForegroundColor Yellow
Write-Host "  1. 将 agent_hub_deploy.zip 上传到服务器" -ForegroundColor White
Write-Host "  2. 在服务器上解压到 C:\package" -ForegroundColor White
Write-Host "  3. 运行 scripts\install_service.ps1" -ForegroundColor White
Write-Host ""
Write-Host "上传方式:" -ForegroundColor Yellow
Write-Host "  - 远程桌面复制粘贴" -ForegroundColor White
Write-Host "  - 腾讯云控制台上传" -ForegroundColor White
Write-Host "  - scp 命令 (需要配置 SSH)" -ForegroundColor White
Write-Host ""
pause
