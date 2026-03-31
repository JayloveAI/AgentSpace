#!/bin/bash
#===============================================================================
# AgentHub V1.5 一键部署脚本
#===============================================================================
# 在云服务器上直接执行此脚本来完成部署
#
# 使用方法：
#   curl -fsSL https://your-server/deploy.sh | bash
#   或者下载后: bash one_click_deploy.sh
#===============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AgentHub V1.5 一键部署${NC}"
echo -e "${BLUE}========================================${NC}\n"

#-------------------------------------------------------------------------------
# 配置
#-------------------------------------------------------------------------------

DEPLOY_PATH="/opt/agent-hub"
BACKUP_PATH="${DEPLOY_PATH}_backup_$(date +%Y%m%d_%H%M%S)"
DB_NAME="agent_hub"
DB_USER="agenthub"

#-------------------------------------------------------------------------------
# 步骤 1: 备份现有部署
#-------------------------------------------------------------------------------

echo -e "${BLUE}[1/6] 备份现有部署...${NC}"

if [ -d "$DEPLOY_PATH" ]; then
    sudo cp -r $DEPLOY_PATH $BACKUP_PATH
    echo -e "${GREEN}✓ 已备份到: $BACKUP_PATH${NC}"
else
    echo -e "${YELLOW}首次部署，跳过备份${NC}"
fi

#-------------------------------------------------------------------------------
# 步骤 2: 创建目录
#-------------------------------------------------------------------------------

echo -e "${BLUE}[2/6] 创建部署目录...${NC}"

sudo mkdir -p $DEPLOY_PATH/{hub_server/{api,db,db/migrations,services},client_sdk/{cli,core,daemon,tunnel,webhook},scripts}
echo -e "${GREEN}✓ 目录创建完成${NC}"

#-------------------------------------------------------------------------------
# 步骤 3: 下载/更新文件
#-------------------------------------------------------------------------------

echo -e "${BLUE}[3/6] 更新代码文件...${NC}"

# 注意: 这里需要你手动上传文件或使用 git clone
# 如果你的代码在 git 仓库:
# if [ -d "$DEPLOY_PATH/.git" ]; then
#     cd $DEPLOY_PATH && git pull
# else
#     git clone https://github.com/your-repo/agent-hub.git $DEPLOY_PATH
# fi

echo -e "${YELLOW}请确保已将代码上传到: $DEPLOY_PATH${NC}"

#-------------------------------------------------------------------------------
# 步骤 4: 安装依赖
#-------------------------------------------------------------------------------

echo -e "${BLUE}[4/6] 安装 Python 依赖...${NC}"

cd $DEPLOY_PATH

# 创建虚拟环境
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# 安装依赖
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo -e "${GREEN}✓ 依赖安装完成${NC}"

#-------------------------------------------------------------------------------
# 步骤 5: 数据库迁移
#-------------------------------------------------------------------------------

echo -e "${BLUE}[5/6] 运行数据库迁移...${NC}"

if [ -f "hub_server/db/migrations/002_add_live_status.sql" ]; then
    # 检查迁移是否已执行
    MIGRATION_DONE=$(sudo -u postgres psql -d $DB_NAME -tAc "SELECT 1 FROM pg_type WHERE typname = 'node_status_enum'" 2>/dev/null || echo "")

    if [ -z "$MIGRATION_DONE" ]; then
        echo "执行 V1.5 数据库迁移..."
        sudo -u postgres psql -d $DB_NAME -f hub_server/db/migrations/002_add_live_status.sql
        echo -e "${GREEN}✓ 数据库迁移完成${NC}"
    else
        echo -e "${YELLOW}数据库迁移已执行过，跳过${NC}"
    fi
else
    echo -e "${YELLOW}迁移文件不存在，跳过数据库迁移${NC}"
fi

#-------------------------------------------------------------------------------
# 步骤 6: 重启服务
#-------------------------------------------------------------------------------

echo -e "${BLUE}[6/6] 重启 Hub 服务...${NC}"

# 创建/更新 systemd 服务
sudo tee /etc/systemd/system/agent-hub.service > /dev/null << EOF
[Unit]
Description=Agent Universal Hub V1.5
After=network.target postgresql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$DEPLOY_PATH
Environment="PATH=$DEPLOY_PATH/venv/bin:/usr/bin"
ExecStart=$DEPLOY_PATH/venv/bin/uvicorn hub_server.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 重新加载并重启
sudo systemctl daemon-reload
sudo systemctl enable agent-hub
sudo systemctl restart agent-hub

# 等待服务启动
sleep 3

# 检查服务状态
if systemctl is-active --quiet agent-hub; then
    echo -e "${GREEN}✓ Hub 服务已启动${NC}"
else
    echo -e "${YELLOW}⚠ 服务启动失败，查看日志:${NC}"
    sudo journalctl -u agent-hub -n 20 --no-pager
fi

#-------------------------------------------------------------------------------
# 验证部署
#-------------------------------------------------------------------------------

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}部署完成！${NC}"
echo -e "${BLUE}========================================${NC}\n"

echo "服务状态:"
sudo systemctl status agent-hub --no-pager | head -n 10

echo ""
echo "API 文档: http://$(hostname -I | awk '{print $1}'):8000/docs"
echo "健康检查: http://$(hostname -I | awk '{print $1}'):8000/health"
echo ""
echo "常用命令:"
echo "  查看日志: sudo journalctl -u agent-hub -f"
echo "  重启服务: sudo systemctl restart agent-hub"
echo "  停止服务: sudo systemctl stop agent-hub"
echo ""
