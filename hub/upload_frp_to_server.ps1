# 上传 FRP 配置到云服务器
# 使用方式：.\upload_frp_to_server.ps1

$Server = "your-server-ip"
$Username = "Administrator"  # 修改为你的云服务器用户名
$Password = ConvertTo-SecureString "你的密码" -AsPlainText -Force  # 修改为你的密码
$Credential = New-Object System.Management.Automation.PSCredential($Username, $Password)

# FRP 配置内容
$FrpsConfig = @"
[common]
bind_port = 7000
vhost_http_port = 8080
token = your-frp-token-here
"@

# 远程执行
Invoke-Command -ComputerName $Server -Credential $Credential -ScriptBlock {
    param($config)
    $config | Out-File -FilePath "C:\frp\frps.ini" -Encoding ascii
    Write-Host "frps.ini 已创建"
    Get-Content "C:\frp\frps.ini"
} -ArgumentList $FrpsConfig

# 重启 FRP
Invoke-Command -ComputerName $Server -Credential $Credential -ScriptBlock {
    cd C:\frp
    taskkill /F /IM frps.exe 2>$null
    Start-Process -FilePath ".\frps.exe" -ArgumentList "-c frps.ini" -WindowStyle Normal
    Write-Host "FRP 服务端已重启"
}
