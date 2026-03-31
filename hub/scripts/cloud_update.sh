#!/bin/bash
# ============================================================================
# ClawHub Cloud Server Update Script
# Target: Tencent Cloud Lighthouse lhins-10zmw6w0 (your-server-ip)
# Access: BT Panel - Port 8888
# ============================================================================

set -e

SERVER_IP="your-server-ip"
SERVER_USER="administrator"
SERVER_PORT="22"
SERVER_PATH="/www/server/hub"  # 宝塔默认Python项目路径，请根据实际修改

echo "=============================================="
echo "  ClawHub Cloud Update - $(date)"
echo "=============================================="
echo ""

# 1. 备份当前文件
echo "[1/5] Backing up current files on cloud..."
ssh ${SERVER_USER}@${SERVER_IP} " \
    cd ${SERVER_PATH}/services && \
    cp lite_repository.py lite_repository.py.bak.\$(date +%Y%m%d_%H%M%S) && \
    cp match_service.py match_service.py.bak.\$(date +%Y%m%d_%H%M%S) && \
    echo '  Backup completed'
"

# 2. 上传新文件
echo "[2/5] Uploading new files..."
scp hub_server/services/lite_repository.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/services/
scp hub_server/services/match_service.py ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/services/
echo "  Upload completed"

# 3. 安装依赖
echo "[3/5] Installing dependencies on cloud..."
ssh ${SERVER_USER}@${SERVER_IP} "pip3 install numpy --quiet"
echo "  Dependencies installed"

# 4. 重启服务
echo "[4/5] Restarting service..."
ssh ${SERVER_USER}@${SERVER_IP} " \
    if systemctl list-units | grep -q hub; then \
        systemctl restart hub; \
    elif pgrep -f uvicorn > /dev/null; then \
        pkill -f uvicorn; \
        sleep 2; \
        cd ${SERVER_PATH} && nohup python3 -m uvicorn hub_server.main:app --host 0.0.0.0 --port 8000 > /tmp/hub.log 2>&1 & \
    fi; \
    sleep 3; \
    echo '  Service restarted'
"

# 5. 验证
echo "[5/5] Verifying deployment..."
RESULT=$(ssh ${SERVER_USER}@${SERVER_IP} "curl -s http://localhost:8000/health")
echo "  Health check: $RESULT"

if echo "$RESULT" | grep -q "healthy"; then
    echo ""
    echo "=============================================="
    echo "  ✅ Deployment Successful!"
    echo "=============================================="
else
    echo ""
    echo "=============================================="
    echo "  ⚠️  Deployment completed, please verify"
    echo "=============================================="
fi
