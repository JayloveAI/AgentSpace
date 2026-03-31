#===============================================================================
# AgentHub V1.5 云服务器部署脚本 (PowerShell 版本)
#===============================================================================
# 用法：
#   .\scripts\deploy_to_cloud.ps1 -ServerIp "192.168.1.100" -User "ubuntu"
#
# 示例：
#   .\scripts\deploy_to_cloud.ps1 -ServerIp "192.168.1.100" -User "ubuntu" -DeployPath "/opt/agent-hub"
#===============================================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$ServerIp,

    [Parameter(Mandatory=$false)]
    [string]$User = "ubuntu",

    [Parameter(Mandatory=$false)]
    [string]$Port = "22",

    [Parameter(Mandatory=$false)]
    [string]$DeployPath = "/opt/agent-hub",

    [Parameter(Mandatory=$false)]
    [string]$IdentityFile = "~/.ssh/id_rsa"
)

#-------------------------------------------------------------------------------
# 配置
#-------------------------------------------------------------------------------

$ErrorActionPreference = "Stop"

# 本地项目路径
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

# SSH 连接字符串
$SshPrefix = "-p $Port -i $IdentityFile $User@${ServerIp}"

#-------------------------------------------------------------------------------
# 工具函数
#-------------------------------------------------------------------------------

function Write-Step {
    param([string]$Message)
    Write-Host "`n========================================" -ForegroundColor Blue
    Write-Host "$Message" -ForegroundColor Blue
    Write-Host "========================================`n" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Test-SshConnection {
    Write-Step "步骤 1: 测试服务器连接"

    try {
        $result = ssh $SshPrefix.Split(" ") "echo '连接成功'" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "服务器连接正常"
            return $true
        }
    }
    catch {
        Write-Error "无法连接到服务器: $_"
        return $false
    }

    Write-Error "SSH 连接失败，请检查："
    Write-Host "  1. 服务器IP是否正确: $ServerIp"
    Write-Host "  2. SSH密钥是否配置: $IdentityFile"
    Write-Host "  3. 服务器安全组是否开放SSH端口: $Port"
    return $false
}

function Backup-RemoteDeployment {
    Write-Step "步骤 2: 备份现有部署"

    $backupCommand = @"
if [ -d "$DeployPath" ]; then
    BACKUP_DIR="${DeployPath}_backup_$(date +%Y%m%d_%H%M%S)"
    mv $DeployPath $${BACKUP_DIR}
    echo "已备份到: $${BACKUP_DIR}"
else
    echo "首次部署，无需备份"
fi
"@

    ssh $SshPrefix.Split(" ") $backupCommand
    Write-Success "备份完成"
}

function Sync-ProjectFiles {
    Write-Step "步骤 3: 同步代码文件"

    # 创建远程目录
    ssh $SshPrefix.Split(" ") "mkdir -p $DeployPath"

    # 使用 rsync 同步文件
    $rsyncCmd = @"
rsync -avz --delete -e "ssh -p $Port -i $IdentityFile" --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.pytest_cache' --exclude='tests/fixtures' --exclude='*.log' --exclude='.env' --exclude='node_modules' --exclude='package' "$ProjectRoot/" ${User}@${ServerIp}:${DeployPath}/
"@

    # 如果没有 rsync，使用 scp
    $hasRsync = $false
    try {
        $null = Get-Command rsync -ErrorAction Stop
        $hasRsync = $true
    }
    catch {
        Write-Warning "rsync 未安装，将使用 scp（较慢）"
    }

    if ($hasRsync) {
        Invoke-Expression $rsyncCmd
    }
    else {
        # 使用 WinSCP 或 scp
        Write-Host "正在同步文件（这可能需要较长时间）..."
        scp -r -P $Port -i $IdentityFile `
            (Join-Path $ProjectRoot "hub_server") `
            (Join-Path $ProjectRoot "client_sdk") `
            (Join-Path $ProjectRoot "requirements.txt") `
            (Join-Path $ProjectRoot "README.md") `
            (Join-Path $ProjectRoot ".env.example") `
            "${User}@${ServerIp}:${DeployPath}/"
    }

    Write-Success "代码同步完成"
}

function Install-Dependencies {
    Write-Step "步骤 4: 安装 Python 依赖"

    $installCommand = @"
cd $DeployPath

# 检查 Python 版本
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $$2}')
echo "Python 版本: $${PYTHON_VERSION}"

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境并安装依赖
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "依赖安装完成"
"@

    ssh $SshPrefix.Split(" ") $installCommand
    Write-Success "Python 依赖安装完成"
}

function Configure-SystemService {
    Write-Step "步骤 5: 配置 systemd 服务"

    $serviceConfig = @"
[Unit]
Description=Agent Universal Hub V1.5
After=network.target postgresql.service

[Service]
Type=simple
User=$User
WorkingDirectory=$DeployPath
Environment="PATH=$DeployPath/venv/bin"
ExecStart=$DeployPath/venv/bin/uvicorn hub_server.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"@

    $configureCommand = @"
echo '$serviceConfig' | sudo tee /etc/systemd/system/agent-hub.service > /dev/null
sudo systemctl daemon-reload
echo "systemd 服务已配置"
"@

    ssh $SshPrefix.Split(" ") $configureCommand
    Write-Success "systemd 服务配置完成"
}

function Start-HubService {
    Write-Step "步骤 6: 启动服务"

    $response = Read-Host "是否立即启动服务? (y/N)"

    if ($response -eq 'y' -or $response -eq 'Y') {
        $startCommand = @"
sudo systemctl enable agent-hub.service
sudo systemctl start agent-hub.service
sleep 3
sudo systemctl status agent-hub.service --no-pager
"@

        ssh $SshPrefix.Split(" ") $startCommand
        Write-Success "服务已启动"
    }
    else {
        Write-Warning "服务未启动，手动启动命令:"
        Write-Host "  ssh ${User}@${ServerIp} 'sudo systemctl start agent-hub'"
    }
}

function Test-Deployment {
    Write-Step "步骤 7: 验证部署"

    Write-Host "等待服务启动..."
    Start-Sleep -Seconds 3

    try {
        $healthUrl = "http://${ServerIp}:8000/health"
        $response = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 5

        if ($response.status -eq "healthy") {
            Write-Success "Hub 服务运行正常"
            Write-Host "`nAPI 文档: http://${ServerIp}:8000/docs"
            Write-Host "健康检查: $healthUrl"
        }
    }
    catch {
        Write-Warning "健康检查失败，请检查服务日志:"
        Write-Host "  ssh ${User}@${ServerIp} 'sudo journalctl -u agent-hub -n 50'"
    }
}

#-------------------------------------------------------------------------------
# 主流程
#-------------------------------------------------------------------------------

Write-Step "AgentHub V1.5 云服务器部署"
Write-Host "服务器: ${User}@${ServerIp}:${Port}"
Write-Host "部署路径: $DeployPath"
Write-Host "项目根目录: $ProjectRoot"

if (-not (Test-SshConnection)) {
    exit 1
}

Backup-RemoteDeployment
Sync-ProjectFiles
Install-Dependencies
Configure-SystemService
Start-HubService
Test-Deployment

Write-Step "部署完成"

Write-Host "`n后续步骤："
Write-Host "  1. 手动执行数据库迁移"
Write-Host "  2. 配置 .env 文件中的 API 密钥"
Write-Host "  3. 检查防火墙规则 (开放 8000 端口)"
Write-Host "`n常用命令："
Write-Host "  查看日志: sudo journalctl -u agent-hub -f"
Write-Host "  重启服务: sudo systemctl restart agent-hub"
Write-Host "  停止服务: sudo systemctl stop agent-hub"
Write-Host ""
