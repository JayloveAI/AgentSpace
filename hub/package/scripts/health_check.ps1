# AgentSpace Health Check & Auto-Recovery Script
# -*- coding: utf-8 -*-
# Monitors and automatically recovers services

param(
    [int]$IntervalSeconds = 30,
    [switch]$Continuous
)

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$agentspaceDir = Join-Path $env:USERPROFILE ".agentspace"
$frpDir = Join-Path $agentspaceDir "frp"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $color = switch ($Level) {
        "ERROR" { "Red" }
        "WARN" { "Yellow" }
        "OK" { "Green" }
        default { "White" }
    }
    Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor $color
}

function Test-Port {
    param([string]$Host, [int]$Port, [int]$Timeout = 5)
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $connect = $tcp.BeginConnect($Host, $Port, $null, $null)
        $wait = $connect.AsyncWaitHandle.WaitOne($Timeout * 1000)
        if ($wait) {
            $tcp.EndConnect($connect)
            $tcp.Close()
            return $true
        }
        $tcp.Close()
        return $false
    } catch {
        return $false
    }
}

function Test-HttpEndpoint {
    param([string]$Url, [int]$Timeout = 5)
    try {
        $response = Invoke-WebRequest -Uri $Url -TimeoutSec $Timeout -UseBasicParsing
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Restart-Frpc {
    Write-Log "Restarting FRP client..." "WARN"

    Get-Process -Name frpc -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 1

    $frpcExe = Join-Path $frpDir "frpc.exe"
    $frpcToml = Join-Path $frpDir "frpc.toml"

    if (Test-Path $frpcExe) {
        Start-Process -FilePath $frpcExe -ArgumentList "-c", $frpcToml -WindowStyle Hidden
        Write-Log "FRP client restarted" "OK"
        return $true
    }
    return $false
}

function Restart-AgentSpace {
    Write-Log "Restarting AgentSpace..." "WARN"

    $port8000 = netstat -ano | Select-String ":8000\s+" | Select-String "LISTENING"
    if ($port8000) {
        $pidStr = ($port8000 -split '\s+')[-1]
        $pid = [int]$pidStr
        if ($pid -and $pid -gt 0) {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }

    Start-Sleep -Seconds 1

    try {
        Start-Process -FilePath "agentspace" -ArgumentList "start" -WindowStyle Hidden
        Write-Log "AgentSpace restarted" "OK"
        return $true
    } catch {
        return $false
    }
}

function Invoke-HealthCheck {
    Write-Host ""
    Write-Log "Running health check..." "INFO"

    $issues = @()

    $frpServer = "your-server-ip"
    if (Test-Port -Host $frpServer -Port 7000) {
        Write-Log "FRP Server ($frpServer`:7000): OK" "OK"
    } else {
        Write-Log "FRP Server ($frpServer`:7000): FAILED" "ERROR"
        $issues += "FRP_SERVER"
    }

    $frpcProcess = Get-Process -Name frpc -ErrorAction SilentlyContinue
    if ($frpcProcess) {
        Write-Log "FRP Client process: OK (PID: $($frpcProcess.Id))" "OK"
    } else {
        Write-Log "FRP Client process: NOT RUNNING" "ERROR"
        $issues += "FRPC_PROCESS"
    }

    if (Test-HttpEndpoint -Url "http://127.0.0.1:8000/health") {
        Write-Log "Local Webhook: OK" "OK"
    } else {
        Write-Log "Local Webhook: FAILED" "ERROR"
        $issues += "WEBHOOK"
    }

    if (Test-HttpEndpoint -Url "http://your-server-ip:8000/health" -Timeout 10) {
        Write-Log "Hub Server: OK" "OK"
    } else {
        Write-Log "Hub Server: FAILED (may need manual restart)" "WARN"
        $issues += "HUB_SERVER"
    }

    if ($issues.Count -gt 0) {
        Write-Log "Attempting auto-recovery..." "WARN"

        if ($issues -contains "FRPC_PROCESS") {
            Restart-Frpc
            Start-Sleep -Seconds 2
        }

        if ($issues -contains "WEBHOOK") {
            Restart-AgentSpace
            Start-Sleep -Seconds 3
        }

        Write-Log "Re-checking after recovery..." "INFO"

        $frpcProcess = Get-Process -Name frpc -ErrorAction SilentlyContinue
        if ($frpcProcess) {
            Write-Log "FRP Client: Recovered" "OK"
        }

        if (Test-HttpEndpoint -Url "http://127.0.0.1:8000/health") {
            Write-Log "Webhook: Recovered" "OK"
        }
    }

    return $issues.Count -eq 0
}

if ($Continuous) {
    Write-Log "Starting continuous health monitoring (interval: ${IntervalSeconds}s)" "INFO"
    Write-Log "Press Ctrl+C to stop" "INFO"

    while ($true) {
        Invoke-HealthCheck
        Start-Sleep -Seconds $IntervalSeconds
    }
} else {
    $success = Invoke-HealthCheck
    if ($success) {
        Write-Host ""
        Write-Log "All services healthy!" "OK"
        exit 0
    } else {
        Write-Host ""
        Write-Log "Some issues could not be auto-recovered" "ERROR"
        exit 1
    }
}
