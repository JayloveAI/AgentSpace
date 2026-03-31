# ClawHub V1.5 隧道配置指南

## 测试结果摘要

```
[OK] 通过: 2
[INFO] 失败: 0
[WARN] 跳过: 2
```

**核心功能已验证**：
- TunnelManager 生命周期管理 ✓
- 跨设备 P2P 流程模拟 ✓

**需要配置**：
- Ngrok Token (用于真实隧道测试)
- FRP Server (用于国内隧道测试)

---

## 快速开始：Ngrok 配置

### 1. 获取 Ngrok Token

访问 https://dashboard.ngrok.com/get-started/your-authtoken

### 2. 设置环境变量

**Windows (PowerShell)**:
```powershell
$env:NGROK_AUTHTOKEN="your_token_here"
# 或永久设置
[System.Environment]::SetEnvironmentVariable('NGROK_AUTHTOKEN', 'your_token_here', 'User')
```

**Windows (CMD)**:
```cmd
set NGROK_AUTHTOKEN=your_token_here
# 或永久设置
setx NGROK_AUTHTOKEN "your_token_here"
```

**Linux/Mac**:
```bash
export NGROK_AUTHTOKEN="your_token_here"
# 添加到 ~/.bashrc 或 ~/.zshrc
echo 'export NGROK_AUTHTOKEN="your_token_here"' >> ~/.bashrc
```

### 3. 运行测试

```bash
python tests/test_tunnel_real.py
```

### 4. 预期输出

成功配置后应看到：

```
[Test 1] Ngrok 隧道启动测试
----------------------------------------
[INFO] 正在启动 Ngrok 隧道 (端口 8000)...
[OK]   Ngrok 隧道启动成功！
[INFO] 公网地址: https://abc1-234-567.ngrok.app
[INFO] 收货 Webhook: https://abc1-234-567.ngrok.app/api/webhook/delivery
[INFO] Ngrok 隧道已关闭
```

---

## 国内用户：FRP 配置

### 1. 获取 FRP 服务器

需要自行搭建或使用第三方 FRP 服务。

### 2. 设置环境变量

**Windows**:
```powershell
$env:FRP_SERVER_ADDR="your_frp_server.com"
$env:FRP_SERVER_PORT="7000"
$env:FRP_TOKEN="your_frp_token"
```

**Linux/Mac**:
```bash
export FRP_SERVER_ADDR="your_frp_server.com"
export FRP_SERVER_PORT="7000"
export FRP_TOKEN="your_frp_token"
```

---

## 完整跨设备 P2P 测试

### 测试场景

**设备 A (Seeker)**:
```python
# 1. 启动 Ngrok 隧道
from client_sdk.tunnel.manager import TunnelManager

manager = TunnelManager(port=8000)
public_url = await manager.start()
# 输出: https://abc123.ngrok.app

# 2. 发布需求（携带 webhook_url）
from client_sdk.gateway.router import UniversalResourceGateway

gateway = UniversalResourceGateway()
gateway.public_base_url = public_url  # 设置公网 URL
demand_id = await gateway.publish_bounty_in_background(...)
```

**设备 B (Provider)**:
```python
# 1. 从 Hub 获取匹配需求（包含 seeker_webhook_url）
matched_demand = {
    "demand_id": "demand-001",
    "seeker_webhook_url": "https://abc123.ngrok.app/api/webhook/delivery",
    # ...
}

# 2. 直接向 Seeker 的公网地址投递文件
from client_sdk.webhook.sender import P2PSender

sender = P2PSender()
success = await sender.send_file_to_seeker(
    matched_demand,
    file_path="/path/to/file.csv",
    provider_id="provider-001"
)
```

### 验证清单

- [ ] 设备 A 启动隧道，获取公网 URL
- [ ] 设备 A 发布需求，携带 seeker_webhook_url
- [ ] Hub 接收需求，存储 webhook_url
- [ ] 设备 B 匹配需求，获取 seeker_webhook_url
- [ ] 设备 B 直接向设备 A 的公网地址发送文件
- [ ] 设备 A 接收文件，保存到 demand_inbox/
- [ ] 文件内容正确（base64 解码成功）

---

## 故障排查

### Ngrok 启动失败

**错误**: "Ngrok connection failed"

**解决方案**:
1. 检查网络连接
2. 确认 Token 有效
3. 检查 Ngrok 账户状态（免费版有连接限制）

### FRP 启动失败

**错误**: "FRP server unreachable"

**解决方案**:
1. 确认 FRP 服务器地址正确
2. 检查防火墙规则
3. 验证 Token 是否匹配

### 收货地址缺失

**错误**: "订单缺少收货地址！"

**解决方案**:
1. 确认 `public_tunnel_url` 已配置
2. 检查 router.py 中 `_publish_to_hub` 是否携带 `seeker_webhook_url`
3. 验证数据库中 `seeker_webhook_url` 字段有值

---

## 架构优势

完成配置后，ClawHub 将实现：

1. **隧道无关化**：FRP、Ngrok、Cloudflare 自由选择
2. **全球 P2P**：标准 HTTP/HTTPS 直连，无 NAT 穿透问题
3. **云端轻量化**：Hub 只负责匹配，不转发文件
4. **高可扩展性**：1 核 2G 服务器可支撑十万级节点

---

## 下一步

配置好 Ngrok Token 后，运行完整测试：

```bash
# 运行隧道测试
python tests/test_tunnel_real.py

# 运行端到端测试（需要两台设备或两个终端）
python tests/test_e2e_p2p.py
```
