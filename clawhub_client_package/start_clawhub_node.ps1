# ClawHub Node Auto-Start Script
# -*- coding: utf-8 -*-
# Automatically handles: FRP config, port conflicts, service startup

param(
    [string]$Mode = "start"
)

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  ClawHub Node - Auto Start" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$clawhubDir = Join-Path $env:USERPROFILE ".clawhub"
$frpDir = Join-Path $clawhubDir "frp"

# [1/5] Load configuration
Write-Host "[1/5] Loading configuration..." -ForegroundColor Yellow

# Load .env
$envFile = Join-Path $clawhubDir ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^([^#][^=]+)=(.*)$") {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            Set-Item -Path "env:$key" -Value $value
        }
    }
    Write-Host "  Loaded .env configuration" -ForegroundColor Green
} else {
    Write-Host "  WARNING: .env file not found at $envFile" -ForegroundColor Yellow
    Write-Host "  Run deploy_all.ps1 first to create configuration" -ForegroundColor Yellow
}

# Load Agent ID
$agentIdFile = Join-Path $clawhubDir ".agent_id"
if (Test-Path $agentIdFile) {
    $agentId = Get-Content $agentIdFile -Raw
    $agentId = $agentId.Trim()
    Write-Host "  Agent ID: $agentId" -ForegroundColor Cyan
} else {
    $agentId = "agent-" + [Guid]::NewGuid().ToString().Substring(0, 8)
    $agentId | Out-File -FilePath $agentIdFile -Encoding UTF8 -NoNewline
    Write-Host "  Generated Agent ID: $agentId" -ForegroundColor Green
}

# [2/5] Fix FRP configuration
Write-Host "[2/5] Configuring FRP..." -ForegroundColor Yellow

$frpcToml = Join-Path $frpDir "frpc.toml"
$frpToken = "your-frp-token-here"
$serverAddr = if ($env:FRP_SERVER_ADDR) { $env:FRP_SERVER_ADDR } else { "your-server-ip" }
$serverPort = if ($env:FRP_SERVER_PORT) { $env:FRP_SERVER_PORT } else { "7000" }

# Calculate deterministic remote port
$sha256 = [System.Security.Cryptography.SHA256]::Create()
$hashBytes = $sha256.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($agentId))
$portOffset = [BitConverter]::ToInt32($hashBytes, 0) -band 0x7FFFFFFF
$remotePort = 8001 + ($portOffset % 999)

# Use unique proxy name to avoid conflicts
$proxyName = "webhook_$($agentId -replace 'agent-','')"

$frpConfig = @"
serverAddr = "$serverAddr"
serverPort = $serverPort
auth.token = "$frpToken"

[[proxies]]
name = "$proxyName"
type = "tcp"
localIP = "127.0.0.1"
localPort = 8000
remotePort = $remotePort
"@

[System.IO.File]::WriteAllText($frpcToml, $frpConfig, [System.Text.UTF8Encoding]::new($false))
Write-Host "  FRP Token: configured" -ForegroundColor Green
Write-Host "  Remote Port: $remotePort" -ForegroundColor Green
Write-Host "  Proxy Name: $proxyName" -ForegroundColor Green
Write-Host "  Config: $frpcToml" -ForegroundColor Cyan

# [3/5] Kill existing FRP processes
Write-Host "[3/5] Cleaning up old processes..." -ForegroundColor Yellow

$frpcProcesses = Get-Process -Name frpc -ErrorAction SilentlyContinue
if ($frpcProcesses) {
    foreach ($proc in $frpcProcesses) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        Write-Host "  Killed frpc process $($proc.Id)" -ForegroundColor Green
    }
    Start-Sleep -Seconds 1
} else {
    Write-Host "  No existing frpc processes" -ForegroundColor Cyan
}

# Kill any process on local port 8000
$port8000 = netstat -ano | Select-String ":8000\s+" | Select-String "LISTENING"
if ($port8000) {
    $pidStr = ($port8000 -split '\s+')[-1]
    $pid = [int]$pidStr
    if ($pid -and $pid -gt 0) {
        try {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Host "  Freed port 8000 (killed PID $pid)" -ForegroundColor Green
        } catch {}
    }
}

# [4/5] Start FRP client
Write-Host "[4/5] Starting FRP client..." -ForegroundColor Yellow

$frpcExe = Join-Path $frpDir "frpc.exe"
if (-not (Test-Path $frpcExe)) {
    Write-Host "  ERROR: frpc.exe not found at $frpcExe" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Start-Process -FilePath $frpcExe -ArgumentList "-c", $frpcToml -WindowStyle Hidden
Write-Host "  FRP client started" -ForegroundColor Green

Start-Sleep -Seconds 2

# [5/5] Start ClawHub
Write-Host "[5/5] Starting ClawHub..." -ForegroundColor Yellow

try {
    $clawhubProcess = Start-Process -FilePath "clawhub" -ArgumentList "start" -PassThru
    Write-Host "  ClawHub started (PID: $($clawhubProcess.Id))" -ForegroundColor Green
} catch {
    Write-Host "  Failed to start clawhub: $_" -ForegroundColor Yellow
    Write-Host "  Trying python -m client_sdk..." -ForegroundColor Cyan
    python -m client_sdk start
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  ClawHub Node Started" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Agent ID:     $agentId" -ForegroundColor White
Write-Host "  Webhook URL:  http://$serverAddr`:$remotePort" -ForegroundColor White
Write-Host "  Local Health: http://127.0.0.1:8000/health" -ForegroundColor White
