# AgentSpace Deployment Verification Script
# -*- coding: utf-8 -*-
# Run this script to verify your AgentSpace installation

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  AgentSpace Deployment Verification" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$errors = @()
$warnings = @()

Write-Host "[1] Checking Python..." -ForegroundColor Yellow
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    $pythonVersion = python --version 2>&1
    Write-Host "    OK: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "    FAIL: Python not found" -ForegroundColor Red
    $errors += "Python"
}

Write-Host "[2] Checking AgentSpace SDK..." -ForegroundColor Yellow
$sdk = pip show agentspace-sdk 2>$null
if ($sdk) {
    $version = ($sdk | Select-String "Version:").ToString().Replace("Version:", "").Trim()
    Write-Host "    OK: agentspace-sdk $version" -ForegroundColor Green
} else {
    Write-Host "    FAIL: agentspace-sdk not installed" -ForegroundColor Red
    $errors += "SDK"
}

Write-Host "[3] Checking agentspace CLI..." -ForegroundColor Yellow
$cli = Get-Command agentspace -ErrorAction SilentlyContinue
if ($cli) {
    Write-Host "    OK: agentspace command available" -ForegroundColor Green
    Write-Host "         Location: $($cli.Source)" -ForegroundColor Cyan
} else {
    Write-Host "    FAIL: agentspace command not in PATH" -ForegroundColor Red
    $errors += "CLI"
}

Write-Host "[4] Checking FRP client..." -ForegroundColor Yellow
$frpcExe = Join-Path $env:USERPROFILE ".agentspace\frp\frpc.exe"
if (Test-Path $frpcExe) {
    Write-Host "    OK: frpc.exe installed" -ForegroundColor Green
    Write-Host "         Location: $frpcExe" -ForegroundColor Cyan
} else {
    Write-Host "    FAIL: frpc.exe not found" -ForegroundColor Red
    $errors += "FRP"
}

Write-Host "[5] Checking FRP configuration..." -ForegroundColor Yellow
$frpcIni = Join-Path $env:USERPROFILE ".agentspace\frp\frpc.toml"
if (Test-Path $frpcIni) {
    $frpConfig = Get-Content $frpcIni -Raw
    if ($frpConfig -match "auth.token = ""your-frp-token-here""") {
        Write-Host "    OK: FRP token configured correctly" -ForegroundColor Green
    } else {
        Write-Host "    FAIL: FRP token incorrect" -ForegroundColor Red
        $errors += "FRP Token"
    }

    if ($frpConfig -match "remotePort = (\d+)") {
        $remotePort = $matches[1]
        Write-Host "         Remote Port: $remotePort" -ForegroundColor Cyan
    }
} else {
    Write-Host "    FAIL: frpc.toml not found" -ForegroundColor Red
    $errors += "FRP Config"
}

Write-Host "[6] Checking .env configuration..." -ForegroundColor Yellow
$envFile = Join-Path $env:USERPROFILE ".agentspace\.env"
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile -Raw
    Write-Host "    OK: .env file exists" -ForegroundColor Green

    if ($envContent -match "HUB_URL=http://your-server-ip:8000") {
        Write-Host "         HUB_URL: configured" -ForegroundColor Cyan
    }
    if ($envContent -match "AGENT_ID=agent-") {
        Write-Host "         AGENT_ID: configured" -ForegroundColor Cyan
    }
} else {
    Write-Host "    FAIL: .env file not found" -ForegroundColor Red
    $errors += ".env"
}

Write-Host "[7] Checking Agent ID..." -ForegroundColor Yellow
$agentIdFile = Join-Path $env:USERPROFILE ".agentspace\.agent_id"
if (Test-Path $agentIdFile) {
    $agentId = Get-Content $agentIdFile -Raw
    $agentId = $agentId.Trim()
    Write-Host "    OK: Agent ID = $agentId" -ForegroundColor Green
} else {
    Write-Host "    FAIL: Agent ID not generated" -ForegroundColor Red
    $errors += "Agent ID"
}

Write-Host "[8] Checking workspace directories..." -ForegroundColor Yellow
$agentspaceDir = Join-Path $env:USERPROFILE ".agentspace"
$supplyDir = Join-Path $agentspaceDir "supply_provided"
$demandDir = Join-Path $agentspaceDir "demand_inbox"

$dirsOk = $true
if (Test-Path $supplyDir) {
    Write-Host "    OK: supply_provided/" -ForegroundColor Green
} else {
    Write-Host "    FAIL: supply_provided/ not found" -ForegroundColor Red
    $dirsOk = $false
}

if (Test-Path $demandDir) {
    Write-Host "    OK: demand_inbox/" -ForegroundColor Green
} else {
    Write-Host "    FAIL: demand_inbox/ not found" -ForegroundColor Red
    $dirsOk = $false
}

if (-not $dirsOk) {
    $errors += "Workspace directories"
}

Write-Host "[9] Testing Hub connection..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://your-server-ip:8000/health" -TimeoutSec 10 -UseBasicParsing
    $health = $response.Content | ConvertFrom-Json
    Write-Host "    OK: Hub is reachable" -ForegroundColor Green
    Write-Host "         Status: $($health.status)" -ForegroundColor Cyan
} catch {
    Write-Host "    FAIL: Cannot connect to Hub" -ForegroundColor Red
    $errors += "Hub connection"
}

Write-Host "[10] Testing FRP server connection..." -ForegroundColor Yellow
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $connect = $tcp.BeginConnect("your-server-ip", 7000, $null, $null)
    $wait = $connect.AsyncWaitHandle.WaitOne(5000)
    if ($wait) {
        $tcp.EndConnect($connect)
        Write-Host "    OK: FRP server is reachable" -ForegroundColor Green
    } else {
        Write-Host "    FAIL: FRP server connection timeout" -ForegroundColor Red
        $errors += "FRP server"
    }
    $tcp.Close()
} catch {
    Write-Host "    FAIL: Cannot connect to FRP server" -ForegroundColor Red
    $errors += "FRP server"
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Verification Summary" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

if ($errors.Count -eq 0) {
    Write-Host "  [PASS] All critical checks passed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Ready to start: agentspace start" -ForegroundColor White
    Write-Host "  Or run: .\start_agentspace_node.ps1" -ForegroundColor White
} else {
    Write-Host "  [FAIL] Found $($errors.Count) error(s):" -ForegroundColor Red
    foreach ($e in $errors) {
        Write-Host "    - $e" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "  Please run install_all.ps1 to fix these issues" -ForegroundColor Yellow
}

Write-Host ""
