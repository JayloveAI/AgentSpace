# 将 Hub Server 注册为 Windows 服务
# 需要 NSSM (Non-Sucking Service Manager)

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  Agent Hub Windows 服务安装" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# 检查管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[错误] 请以管理员身份运行此脚本" -ForegroundColor Red
    exit 1
}

# 检查 Python
Write-Host "[1/5] 检查 Python..." -ForegroundColor Yellow
try {
    $pythonPath = (Get-Command python).Source
    Write-Host "  Python 路径: $pythonPath" -ForegroundColor Green
} catch {
    Write-Host "  Python 未安装" -ForegroundColor Red
    exit 1
}

# 下载 NSSM
Write-Host "[2/5] 下载 NSSM..." -ForegroundColor Yellow
$nssmPath = "C:\agent-hub\nssm.exe"
if (-not (Test-Path $nssmPath)) {
    $nssmUrl = "https://nssm.cc/release/nssm-2.24-101-g897c7ad.zip"
    $nssmZip = "C:\agent-hub\nssm.zip"
    Invoke-WebRequest -Uri $nssmUrl -OutFile $nssmZip
    Expand-Archive -Path $nssmZip -DestinationPath "C:\agent-hub\nssm_temp" -Force
    Copy-Item "C:\agent-hub\nssm_temp\nssm-2.24-101-g897c7ad\win64\nssm.exe" -Destination "C:\agent-hub\"
    Remove-Item "C:\agent-hub\nssm_temp" -Recurse -Force
    Remove-Item $nssmZip -Force
    Write-Host "  NSSM 已下载" -ForegroundColor Green
} else {
    Write-Host "  NSSM 已存在" -ForegroundColor Green
}

# 创建启动脚本
Write-Host "[3/5] 创建启动脚本..." -ForegroundColor Yellow
$startScript = @'
@echo off
cd /d C:\agent-hub
python -m uvicorn hub_server.main:app --host 0.0.0.0 --port 8000
'@
$startScript | Out-File -FilePath "C:\agent-hub\start_service.bat" -Encoding Default

# 安装服务
Write-Host "[4/5] 安装 Windows 服务..." -ForegroundColor Yellow
& $nssmPath install AgentHub "C:\agent-hub\start_service.bat"
& $nssmPath set AgentHub AppDirectory "C:\agent-hub"
& $nssmPath set AgentHub DisplayName "Agent Universal Hub"
& $nssmPath set AgentHub Description "AI Agent Matchmaking Hub Server"
& $nssmPath set AgentHub Start SERVICE_AUTO_START

# 配置服务重启
& $nssmPath set AgentHub AppRestartDelay 10000
& $nssmPath set AgentHub AppThrottle 1500
& $nssmPath set AgentHub AppExit Default Restart
& $nssmPath set AgentHub AppRestartDelay 10000

Write-Host "  服务已安装" -ForegroundColor Green

# 配置防火墙
Write-Host "[5/5] 配置防火墙..." -ForegroundColor Yellow
try {
    New-NetFirewallRule -DisplayName "Agent Hub (HTTP)" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow -ErrorAction SilentlyContinue
    Write-Host "  防火墙规则已添加" -ForegroundColor Green
} catch {
    Write-Host "  防火墙配置失败，请手动添加" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "  安装完成！" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "服务管理命令:" -ForegroundColor Cyan
Write-Host "  启动服务: nssm start AgentHub" -ForegroundColor White
Write-Host "  停止服务: nssm stop AgentHub" -ForegroundColor White
Write-Host "  重启服务: nssm restart AgentHub" -ForegroundColor White
Write-Host "  卸载服务: nssm remove AgentHub" -ForegroundColor White
Write-Host "  查看状态: nssm status AgentHub" -ForegroundColor White
Write-Host ""
Write-Host "启动服务:" -ForegroundColor Yellow
nssm start AgentHub
Write-Host ""
Write-Host "服务访问地址: http://your-server-ip:8000/docs" -ForegroundColor Green
Write-Host ""
pause
