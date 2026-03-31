#!/bin/bash
#===============================================================================
# AgentHub V1.5 云服务器部署脚本
#===============================================================================
# 用法：
#   1. 本地打包：bash scripts/build_package.sh
#   2. 上传部署：bash scripts/deploy_to_cloud.sh <server_ip> <user>
#
# 示例：
#   bash scripts/deploy_to_cloud.sh 192.168.1.100 ubuntu
#===============================================================================

set -e  # 遇到错误立即退出

#-------------------------------------------------------------------------------
# 配置区域
#-------------------------------------------------------------------------------

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 服务器配置
SERVER_IP=${1:-""}
SERVER_USER=${2:-"ubuntu"}
SERVER_PORT=${3:-"22"}
DEPLOY_PATH=${4:-"/opt/agent-hub"}

# 检查参数
if [ -z "$SERVER_IP" ]; then
    echo -e "${RED}错误: 请提供服务器IP地址${NC}"
    echo "用法: bash $0 <server_ip> [user] [port] [deploy_path]"
    echo "示例: bash $0 192.168.1.100 ubuntu 22 /opt/agent-hub"
    exit 1
fi

#-------------------------------------------------------------------------------
# 打印函数
#-------------------------------------------------------------------------------

print_step() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

#-------------------------------------------------------------------------------
# 部署流程
#-------------------------------------------------------------------------------

print_step "AgentHub V1.5 云服务器部署"
echo "服务器: ${SERVER_USER}@${SERVER_IP}:${SERVER_PORT}"
echo "部署路径: ${DEPLOY_PATH}"
echo ""

#-------------------------------------------------------------------------------
# 步骤 1: 测试服务器连接
#-------------------------------------------------------------------------------

print_step "步骤 1: 测试服务器连接"

ssh -p ${SERVER_PORT} -o ConnectTimeout=10 ${SERVER_USER}@${SERVER_IP} "echo '连接成功'" || {
    print_error "无法连接到服务器，请检查："
    echo "  1. 服务器IP是否正确"
    echo "  2. SSH密钥是否配置"
    echo "  3. 服务器安全组是否开放SSH端口"
    exit 1
}

print_success "服务器连接正常"

#-------------------------------------------------------------------------------
# 步骤 2: 备份现有部署
#-------------------------------------------------------------------------------

print_step "步骤 2: 备份现有部署"

ssh -p ${SERVER_PORT} ${SERVER_USER}@${SERVER_IP} << ENDSSH
    if [ -d "${DEPLOY_PATH}" ]; then
        BACKUP_DIR="${DEPLOY_PATH}_backup_\$(date +%Y%m%d_%H%M%S)"
        mv ${DEPLOY_PATH} \${BACKUP_DIR}
        echo "已备份到: \${BACKUP_DIR}"
    else
        echo "首次部署，无需备份"
    fi
ENDSSH

print_success "备份完成"

#-------------------------------------------------------------------------------
# 步骤 3: 同步代码文件
#-------------------------------------------------------------------------------

print_step "步骤 3: 同步代码文件"

# 创建远程目录
ssh -p ${SERVER_PORT} ${SERVER_USER}@${SERVER_IP} "mkdir -p ${DEPLOY_PATH}"

# 同步文件（排除不必要的文件）
rsync -avz --delete \
    -e "ssh -p ${SERVER_PORT}" \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='tests/fixtures' \
    --exclude='*.log' \
    --exclude='.env' \
    --exclude='node_modules' \
    --exclude='package' \
    ./ \
    ${SERVER_USER}@${SERVER_IP}:${DEPLOY_PATH}/

print_success "代码同步完成"

#-------------------------------------------------------------------------------
# 步骤 4: 运行数据库迁移
#-------------------------------------------------------------------------------

print_step "步骤 4: 运行数据库迁移"

ssh -p ${SERVER_PORT} ${SERVER_USER}@${SERVER_IP} << ENDSSH
    cd ${DEPLOY_PATH}

    # 检查迁移文件是否存在
    if [ -f "hub_server/db/migrations/002_add_live_status.sql" ]; then
        echo "执行 V1.5 数据库迁移..."

        # 检查 PostgreSQL 是否运行
        if ! systemctl is-active --quiet postgresql; then
            echo "警告: PostgreSQL 未运行，尝试启动..."
            sudo systemctl start postgresql || true
        fi

        # 执行迁移（需要配置数据库连接）
        echo "请手动执行以下命令完成数据库迁移："
        echo ""
        echo "  sudo -u postgres psql agent_hub < ${DEPLOY_PATH}/hub_server/db/migrations/002_add_live_status.sql"
        echo ""
    else
        echo "迁移文件不存在，跳过数据库迁移"
    fi
ENDSSH

print_warning "数据库迁移需要在服务器上手动执行"

#-------------------------------------------------------------------------------
# 步骤 5: 安装/更新 Python 依赖
#-------------------------------------------------------------------------------

print_step "步骤 5: 安装/更新 Python 依赖"

ssh -p ${SERVER_PORT} ${SERVER_USER}@${SERVER_IP} << ENDSSH
    cd ${DEPLOY_PATH}

    # 检查 Python 版本
    PYTHON_VERSION=\$(python3 --version 2>&1 | awk '{print \$2}')
    echo "Python 版本: \${PYTHON_VERSION}"

    # 创建虚拟环境（如果不存在）
    if [ ! -d "venv" ]; then
        echo "创建虚拟环境..."
        python3 -m venv venv
    fi

    # 激活虚拟环境并安装依赖
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt

    echo "依赖安装完成"
ENDSSH

print_success "Python 依赖安装完成"

#-------------------------------------------------------------------------------
# 步骤 6: 配置环境变量
#-------------------------------------------------------------------------------

print_step "步骤 6: 配置环境变量"

ssh -p ${SERVER_PORT} ${SERVER_USER}@${SERVER_IP} << ENDSSH
    cd ${DEPLOY_PATH}

    if [ ! -f ".env" ]; then
        echo "创建 .env 配置文件..."
        cp .env.example .env

        echo ""
        echo "请编辑 .env 文件配置以下关键参数："
        echo "  - GLM_API_KEY: GLM-5 API密钥"
        echo "  - DATABASE_URL: PostgreSQL 连接字符串"
        echo "  - HUB_JWT_SECRET: JWT 签名密钥"
        echo ""
        echo "编辑命令: vi ${DEPLOY_PATH}/.env"
    else
        echo ".env 文件已存在，保留现有配置"
    fi
ENDSSH

print_warning "请检查 .env 配置是否正确"

#-------------------------------------------------------------------------------
# 步骤 7: 配置 systemd 服务
#-------------------------------------------------------------------------------

print_step "步骤 7: 配置 systemd 服务"

ssh -p ${SERVER_PORT} ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
    # 创建 systemd 服务文件
    sudo tee /etc/systemd/system/agent-hub.service > /dev/null << EOF
[Unit]
Description=Agent Universal Hub V1.5
After=network.target postgresql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/agent-hub
Environment="PATH=/opt/agent-hub/venv/bin"
ExecStart=/opt/agent-hub/venv/bin/uvicorn hub_server.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # 重新加载 systemd
    sudo systemctl daemon-reload

    echo "systemd 服务已配置"
ENDSSH

print_success "systemd 服务配置完成"

#-------------------------------------------------------------------------------
# 步骤 8: 启动服务
#-------------------------------------------------------------------------------

print_step "步骤 8: 启动服务"

read -p "是否立即启动服务? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    ssh -p ${SERVER_PORT} ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
        # 启用开机自启
        sudo systemctl enable agent-hub.service

        # 启动服务
        sudo systemctl start agent-hub.service

        # 等待服务启动
        sleep 3

        # 检查服务状态
        sudo systemctl status agent-hub.service --no-pager
ENDSSH

    print_success "服务已启动"
else
    print_warning "服务未启动，手动启动命令:"
    echo "  ssh ${SERVER_USER}@${SERVER_IP} 'sudo systemctl start agent-hub'"
fi

#-------------------------------------------------------------------------------
# 步骤 9: 验证部署
#-------------------------------------------------------------------------------

print_step "步骤 9: 验证部署"

echo "等待服务启动..."
sleep 3

# 测试健康检查
HEALTH_URL="http://${SERVER_IP}:8000/health"
if command -v curl &> /dev/null; then
    HEALTH_CHECK=$(curl -s ${HEALTH_URL} 2>/dev/null || echo "failed")
    if [[ $HEALTH_CHECK == *"healthy"* ]]; then
        print_success "Hub 服务运行正常"
        echo ""
        echo "API 文档: http://${SERVER_IP}:8000/docs"
        echo "健康检查: ${HEALTH_URL}"
    else
        print_warning "健康检查失败，请检查服务日志:"
        echo "  ssh ${SERVER_USER}@${SERVER_IP} 'sudo journalctl -u agent-hub -n 50'"
    fi
else
    print_warning "curl 未安装，跳过健康检查"
fi

#-------------------------------------------------------------------------------
# 部署完成
#-------------------------------------------------------------------------------

print_step "部署完成"

echo ""
echo "后续步骤："
echo "  1. 手动执行数据库迁移"
echo "  2. 配置 .env 文件中的 API 密钥"
echo "  3. 检查防火墙规则 (开放 8000 端口)"
echo "  4. 配置域名和 SSL (可选)"
echo ""
echo "常用命令："
echo "  查看日志: sudo journalctl -u agent-hub -f"
echo "  重启服务: sudo systemctl restart agent-hub"
echo "  停止服务: sudo systemctl stop agent-hub"
echo ""
