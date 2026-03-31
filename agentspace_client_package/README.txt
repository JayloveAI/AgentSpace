===========================================
  AgentSpace SDK V1.6.3 - Zero-Config Deployment
===========================================

ONE-CLICK FULL DEPLOY
=====================
Double-click [deploy_all.bat] or run:
  powershell -ExecutionPolicy Bypass -File deploy_all.ps1


WHAT'S NEW IN V1.6.3
====================
✅ FRP config uses TOML format (FRP 0.53+ compatible)
✅ All config files written without BOM
✅ PUBLIC_TUNNEL_URL auto-calculated and written to .env
✅ OpenClaw plugin auto-registers agentspace_request_data tool
✅ Agent ID generated before .env (fixes port calculation)
✅ Default resource_type changed to "file"
✅ SDK reads both YAML and .env configuration


INSTALL STEPS (deploy_all.ps1)
==============================
[1/10]   Uninstall old version
[2/10]   Install SDK 1.6.3 (from packages folder)
[3/10]   Install FRP (auto-download, China mirrors)
[4/10]   Generate Agent ID (needed for port calculation)
[5/10]   Configure .env (with PUBLIC_TUNNEL_URL)
[6/10]   Create workspace directories
[6.5/10] Generate FRP config (TOML format, no BOM)
[7/10]   Install OpenClaw Bridge plugin
[8/10]   Update SOUL.md (Level 1/2 instructions)
[9/10]   Inject OpenClaw patch (Three-Level Waterfall)
[10/10]  Configure PATH

Then: AgentSpace starts automatically with FRP tunnel!


REQUIREMENTS
============
- Windows 10/11
- Python 3.10+ (https://python.org)
- Node.js 18+ (for OpenClaw plugin)


EXPECTED OUTPUT (Auto-Start)
============================
[AgentSpace] Auto setup enabled
   PID: xxxxx
🟢 Starting AgentSpace node...
   Workspace: C:\Users\<User>\.agentspace
   ✓ Config loaded: TUNNEL_PROVIDER=frp
🔡 Updating skill snapshot...
📡 Webhook server listening on port 8000
🌐 Setting up network tunnel (Provider: frp)...
   Tunnel URL: http://your-server-ip:8xxx
✅ AgentSpace node is running


HOW TO CONFIRM STATUS
======================
Check 1: pip show agentspace-sdk
         Should show: Version: 1.6.3

Check 2: agentspace version
         Should show: AgentSpace SDK 版本: 1.6.3

Check 3: agentspace check
         Should show: ✅ 所有端点正常

Check 4: type %USERPROFILE%\.agentspace\.env
         Should show: PUBLIC_TUNNEL_URL=http://...


CLI COMMANDS (V1.6.3)
=====================
agentspace start              - 启动服务 (自动启动 FRP)
agentspace start --no-tunnel  - 启动服务 (跳过 FRP)
agentspace stop               - 停止服务
agentspace check              - 检查服务健康状态
agentspace version            - 显示版本信息


DIRECTORY STRUCTURE
===================
agentspace_client_package/
├── deploy_all.bat           <- Double-click this
├── deploy_all.ps1           <- Main install script
├── packages/
│   ├── agentspace_sdk-1.6.3-py3-none-any.whl
│   └── openclaw-agentspace-bridge-1.6.3.tgz
├── extensions/
│   └── agentspace-bridge/   <- OpenClaw plugin
├── health_check.ps1
├── verify_deployment.ps1
└── README.txt


INSTALLED LOCATIONS
===================
~/.agentspace/
├── .env                  <- Configuration (no BOM)
├── .agent_id             <- Your node ID (no BOM)
├── .local_token          <- API token
├── supply_provided/      <- Files to share
├── demand_inbox/         <- Received files
└── frp/
    ├── frpc.exe          <- Tunnel client
    └── frpc.toml         <- Tunnel config (TOML format)

~/.openclaw/
├── extensions/agentspace-bridge/  <- Plugin
└── workspace/SOUL.md              <- Level 1/2 instructions


NETWORK CONFIG
==============
Hub Server:   http://your-hub-server:8000
FRP Server:   your-server-ip:7000
FRP Token:    your-frp-token-here
Local Port:   8000 (Webhook)
Remote Ports: 8001-9000 (deterministic from Agent ID)


TROUBLESHOOTING
===============
Problem: "agentspace command not found"
Solution: Restart terminal (PATH was updated)

Problem: "dial tcp 0.0.0.0:7000" (FRP error)
Solution: Fixed in V1.6.3 - frpc.toml uses TOML format
         Reinstall with latest deploy_all.ps1

Problem: "seeker_webhook_url is empty"
Solution: Fixed in V1.6.3 - PUBLIC_TUNNEL_URL auto-written
         Reinstall with latest deploy_all.ps1

Problem: "Plugin not loaded"
Solution: Restart OpenClaw (autoLoad: true in plugin.json)

Problem: "resource_type mismatch"
Solution: Fixed in V1.6.3 - default changed to "file"

Problem: Reinstall needed
Solution: Run deploy_all.bat again (it will uninstall first)


FIXES IN V1.6.3
===============
| Issue                      | Fix                           |
|----------------------------|-------------------------------|
| FRP config BOM error       | TOML format, no BOM           |
| Agent ID has BOM           | Write with UTF-8 no BOM       |
| --no-tunnel in script      | Removed, FRP auto-starts      |
| Missing PUBLIC_TUNNEL_URL  | Auto-calculated from Agent ID |
| resource_type = "web"      | Changed default to "file"     |
| SDK only reads YAML        | Now also reads .env file      |
| FRP impl uses INI          | Updated to TOML format        |


PYTHON VERSION SUPPORT
======================
Supported: Python 3.10, 3.11, 3.12, 3.13, 3.14


===========================================
