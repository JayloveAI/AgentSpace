#===============================================================================
# AgentHub V1.5 密码登录部署脚本 (Windows)
#===============================================================================
# 使用说明：
#   1. 确保已安装 PuTTY (包含 pscp 和 plink)
#   2. 修改下面的服务器配置
#   3. 运行: .\deploy_with_password.ps1
#
# 下载 PuTTY: https://www.putty.org/
#===============================================================================

param(
    [string]$ServerIp = "your-server-ip",
    [string]$User = "ubuntu",
    [string]$Password = "",  # 留空会提示输入
    [string]$DeployPath = "/opt/agent-hub"
)

#-------------------------------------------------------------------------------
# 配置
#-------------------------------------------------------------------------------

$ErrorActionPreference = "Continue"

# 本地项目路径
$ProjectRoot = "e:\hub"

# PuTTY 路径 (需要根据实际安装位置修改)
$PlinkPath = "C:\Program Files\PuTTY\plink.exe"
$PscpPath = "C:\Program Files\PuTTY\pscp.exe"

# 或者使用 WSL 的 ssh/scp (如果安装了 WSL)
$UseWSL = $false

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

function Invoke-RemoteCommand {
    param([string]$Command)

    if ($UseWSL) {
        $sshCommand = "ssh ${User}@${ServerIp} '$Command'"
        wsl bash -c "$sshCommand"
    }
    else {
        # 使用密码提示
        if ([string]::IsNullOrEmpty($Password)) {
            $cred = Get-Credential -UserName $User -Message "输入 SSH 密码"
            $Password = $cred.GetNetworkCredential().Password
        }

        $cmd = "`"$Command`""
        & $PlinkPath -batch -pw $Password "${User}@${ServerIp}" $cmd 2>&1
    }
}

function Copy-ToServer {
    param(
        [string]$Source,
        [string]$Destination
    )

    if ($UseWSL) {
        wsl scp -r "$Source" "${User}@${ServerIp}:$Destination"
    }
    else {
        & $PscpPath -r -pw $Password "$Source" "${User}@${ServerIp}:$Destination"
    }
}

#-------------------------------------------------------------------------------
# 检查工具
#-------------------------------------------------------------------------------

Write-Step "检查部署工具"

if ($UseWSL) {
    $hasSSH = wsl bash -c "which ssh" 2>$null
    if ($hasSSH) {
        Write-Success "使用 WSL SSH"
    }
    else {
        Write-Warning "WSL SSH 未找到"
        exit 1
    }
}
else {
    if ((Test-Path $PlinkPath) -and (Test-Path $PscpPath)) {
        Write-Success "PuTTY 已安装"
    }
    else {
        Write-Warning "PuTTY 未找到"
        Write-Host "请安装 PuTTY 或设置 `$UseWSL = `$true"
        Write-Host "下载: https://www.putty.org/"
        exit 1
    }
}

#-------------------------------------------------------------------------------
# 测试连接
#-------------------------------------------------------------------------------

Write-Step "测试服务器连接"

try {
    $testResult = Invoke-RemoteCommand "echo '连接成功'"
    if ($testResult -match "连接成功") {
        Write-Success "服务器连接正常"
    }
    else {
        Write-Warning "连接测试返回: $testResult"
    }
}
catch {
    Write-Warning "连接测试失败: $_"
}

#-------------------------------------------------------------------------------
# 备份现有部署
#-------------------------------------------------------------------------------

Write-Step "备份现有部署"

Invoke-RemoteCommand "
if [ -d '$DeployPath' ]; then
    BACKUP_DIR='${DeployPath}_backup_$(date +%Y%m%d_%H%M%S)'
    sudo cp -r $DeployPath $${BACKUP_DIR}
    echo '已备份到: $${BACKUP_DIR}'
else
    echo '首次部署，跳过备份'
fi
"

#-------------------------------------------------------------------------------
# 同步代码文件
#-------------------------------------------------------------------------------

Write-Step "同步代码文件"

# 创建远程目录
Invoke-RemoteCommand "sudo mkdir -p $DeployPath/{hub_server/{api,db,db/migrations,services},client_sdk/{cli,core,daemon,tunnel,webhook},scripts}"

# 上传关键文件
Write-Host "上传文件..."

$filesToUpload = @(
    "hub_server/api/contracts.py",
    "hub_server/api/routes.py",
    "hub_server/services/match_service.py",
    "hub_server/db/schema.py",
    "hub_server/db/migrations/002_add_live_status.sql",
    "client_sdk/cli/prompts.py",
    "client_sdk/daemon/gateway.py",
    "client_sdk/tunnel/manager.py",
    "client_sdk/tunnel/cloudflare_tunnel.py",
    "requirements.txt",
    "scripts/migrate_db.sh",
    "scripts/one_click_deploy.sh"
)

foreach ($file in $filesToUpload) {
    $sourcePath = Join-Path $ProjectRoot $file
    if (Test-Path $sourcePath) {
        Write-Host "  上传: $file"
        $destPath = "$DeployPath/$file"
        $remoteDir = Split-Path $destPath -Parent
        Invoke-RemoteCommand "sudo mkdir -p $remoteDir"

        if ($UseWSL) {
            wsl scp "`"$sourcePath`"" "${User}@${ServerIp}:$destPath"
        }
        else {
            & $PscpPath -pw $Password "`"$sourcePath`"" "${User}@${ServerIp}:$destPath"
        }
    }
}

Write-Success "文件同步完成"

#-------------------------------------------------------------------------------
# 安装依赖
#-------------------------------------------------------------------------------

Write-Step "安装 Python 依赖"

Invoke-RemoteCommand "
cd $DeployPath

# 创建虚拟环境
if [ ! -d 'venv' ]; then
    python3 -m venv venv
fi

# 安装新依赖
source venv/bin/activate
pip install --upgrade pip
pip install rich trycloudflare
"

Write-Success "依赖安装完成"

#-------------------------------------------------------------------------------
# 数据库迁移
#-------------------------------------------------------------------------------

Write-Step "数据库迁移"

Invoke-RemoteCommand "
cd $DeployPath

if [ -f 'hub_server/db/migrations/002_add_live_status.sql' ]; then
    echo '检查迁移状态...'
    MIGRATION_DONE=\$(sudo -u postgres psql -d agent_hub -tAc \"SELECT 1 FROM pg_type WHERE typname = 'node_status_enum'\" 2>/dev/null || echo '')

    if [ -z \"\$MIGRATION_DONE\" ]; then
        echo '执行 V1.5 数据库迁移...'
        sudo -u postgres psql -d agent_hub -f hub_server/db/migrations/002_add_live_status.sql
        echo '✓ 数据库迁移完成'
    else
        echo '数据库迁移已执行过，跳过'
    fi
else
    echo '迁移文件不存在'
fi
"

#-------------------------------------------------------------------------------
# 重启服务
#-------------------------------------------------------------------------------

Write-Step "重启 Hub 服务"

Invoke-RemoteCommand "
# 更新 systemd 服务
sudo tee /etc/systemd/system/agent-hub.service > /dev/null << 'EEOF'
[Unit]
Description=Agent Universal Hub V1.5
After=network.target postgresql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$DeployPath
Environment='PATH=$DeployPath/venv/bin:/usr/bin'
ExecStart=$DeployPath/venv/bin/uvicorn hub_server.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EEOF

# 重载并重启
sudo systemctl daemon-reload
sudo systemctl restart agent-hub

# 等待启动
sleep 3

# 显示状态
sudo systemctl status agent-hub --no-pager | head -n 15
"

Write-Success "服务已重启"

#-------------------------------------------------------------------------------
# 验证部署
#-------------------------------------------------------------------------------

Write-Step "验证部署"

Write-Host "`n访问地址:"
Write-Host "  API 文档: http://${ServerIp}:8000/docs"
Write-Host "  健康检查: http://${ServerIp}:8000/health"
Write-Host "`n常用命令:"
Write-Host "  查看日志: ssh ${User}@${ServerIp} 'sudo journalctl -u agent-hub -f'"
Write-Host "  重启服务: ssh ${User}@${ServerIp} 'sudo systemctl restart agent-hub'"
