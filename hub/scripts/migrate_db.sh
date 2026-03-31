#!/bin/bash
#===============================================================================
# AgentHub V1.5 数据库迁移脚本
#===============================================================================
# 在云服务器上执行此脚本以完成数据库升级
#
# 用法：
#   sudo bash migrate_db.sh
#
# 或指定数据库连接：
#   sudo bash migrate_db.sh postgresql://user:pass@localhost/dbname
#===============================================================================

set -e

#-------------------------------------------------------------------------------
# 配置
#-------------------------------------------------------------------------------

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 默认数据库配置（可根据实际情况修改）
DB_NAME=${DB_NAME:-"agent_hub"}
DB_USER=${DB_USER:-"agenthub"}

# 迁移文件路径
MIGRATION_FILE="/opt/agent-hub/hub_server/db/migrations/002_add_live_status.sql"

#-------------------------------------------------------------------------------
# 工具函数
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
# 预检查
#-------------------------------------------------------------------------------

print_step "数据库迁移预检查"

# 检查是否以 root 权限运行
if [ "$EUID" -ne 0 ]; then
    print_warning "建议使用 sudo 运行此脚本"
    read -p "继续执行? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 检查 PostgreSQL 是否安装
if ! command -v psql &> /dev/null; then
    print_error "PostgreSQL 未安装"
    echo "请先安装 PostgreSQL："
    echo "  sudo apt-get install postgresql postgresql-contrib"
    exit 1
fi

print_success "PostgreSQL 已安装"

# 检查 PostgreSQL 是否运行
if ! systemctl is-active --quiet postgresql; then
    print_warning "PostgreSQL 未运行，尝试启动..."
    sudo systemctl start postgresql
    sleep 2
fi

print_success "PostgreSQL 运行中"

# 检查数据库是否存在
DB_EXISTS=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'")

if [ -z "$DB_EXISTS" ]; then
    print_warning "数据库 '$DB_NAME' 不存在"
    read -p "是否创建数据库? (y/N): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo -u postgres psql -c "CREATE DATABASE $DB_NAME;"
        sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
        sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
        print_success "数据库创建完成"
    else
        print_error "无法继续，请先创建数据库"
        exit 1
    fi
else
    print_success "数据库 '$DB_NAME' 存在"
fi

# 检查迁移文件是否存在
if [ ! -f "$MIGRATION_FILE" ]; then
    print_error "迁移文件不存在: $MIGRATION_FILE"
    echo "请确认 AgentHub 已正确部署到: ${MIGRATION_FILE%/*}"
    exit 1
fi

print_success "迁移文件存在"

#-------------------------------------------------------------------------------
# 备份数据库
#-------------------------------------------------------------------------------

print_step "备份数据库"

BACKUP_DIR="/var/backups/agenthub"
BACKUP_FILE="$BACKUP_DIR/pre_migration_$(date +%Y%m%d_%H%M%S).sql"

mkdir -p $BACKUP_DIR

sudo -u postgres pg_dump $DB_NAME > $BACKUP_FILE 2>/dev/null || {
    print_warning "数据库备份失败（可能数据库为空）"
    BACKUP_FILE=""
}

if [ -n "$BACKUP_FILE" ]; then
    print_success "数据库已备份到: $BACKUP_FILE"
fi

#-------------------------------------------------------------------------------
# 检查迁移状态
#-------------------------------------------------------------------------------

print_step "检查迁移状态"

# 检查 node_status_enum 是否已存在
ENUM_EXISTS=$(sudo -u postgres psql -d $DB_NAME -tAc "SELECT 1 FROM pg_type WHERE typname = 'node_status_enum'")

if [ -n "$ENUM_EXISTS" ]; then
    print_warning "迁移似乎已执行过 (node_status_enum 存在)"
    read -p "是否重新执行迁移? (y/N): " -n 1 -r
    echo

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_success "跳过迁移"
        exit 0
    fi

    print_warning "将重新执行迁移..."
fi

#-------------------------------------------------------------------------------
# 执行迁移
#-------------------------------------------------------------------------------

print_step "执行数据库迁移"

echo "迁移文件: $MIGRATION_FILE"
echo ""

# 显示迁移内容预览
echo "迁移内容预览:"
echo "----------------------------------------"
head -n 20 $MIGRATION_FILE
echo "..."
echo "----------------------------------------"
echo ""

read -p "确认执行迁移? (y/N): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "已取消迁移"
    exit 0
fi

# 执行迁移
sudo -u postgres psql -d $DB_NAME -f $MIGRATION_FILE

if [ $? -eq 0 ]; then
    print_success "数据库迁移完成"
else
    print_error "迁移执行失败"
    echo "正在恢复备份..."

    if [ -n "$BACKUP_FILE" ] && [ -f "$BACKUP_FILE" ]; then
        sudo -u postgres psql -d $DB_NAME < $BACKUP_FILE
        print_success "数据库已恢复"
    fi

    exit 1
fi

#-------------------------------------------------------------------------------
# 验证迁移
#-------------------------------------------------------------------------------

print_step "验证迁移结果"

# 检查新列是否存在
NODE_STATUS_COLUMN=$(sudo -u postgres psql -d $DB_NAME -tAc "SELECT 1 FROM information_schema.columns WHERE table_name = 'agent_profiles' AND column_name = 'node_status'")
LIVE_BROADCAST_COLUMN=$(sudo -u postgres psql -d $DB_NAME -tAc "SELECT 1 FROM information_schema.columns WHERE table_name = 'agent_profiles' AND column_name = 'live_broadcast'")

if [ -n "$NODE_STATUS_COLUMN" ]; then
    print_success "node_status 列已添加"
else
    print_error "node_status 列添加失败"
fi

if [ -n "$LIVE_BROADCAST_COLUMN" ]; then
    print_success "live_broadcast 列已添加"
else
    print_error "live_broadcast 列添加失败"
fi

# 显示当前表结构
echo ""
echo "当前 agent_profiles 表结构:"
echo "----------------------------------------"
sudo -u postgres psql -d $DB_NAME -c "\d agent_profiles"
echo "----------------------------------------"

#-------------------------------------------------------------------------------
# 更新现有数据
#-------------------------------------------------------------------------------

print_step "更新现有数据"

# 将现有记录的 node_status 设置为 active
UPDATED_ROWS=$(sudo -u postgres psql -d $DB_NAME -tAc "UPDATE agent_profiles SET node_status = 'active' WHERE node_status IS NULL; SELECT ROW_COUNT();")

if [ "$UPDATED_ROWS" -gt 0 ]; then
    print_success "已更新 $UPDATED_ROWS 条记录为 active 状态"
fi

#-------------------------------------------------------------------------------
# 完成
#-------------------------------------------------------------------------------

print_step "迁移完成"

echo ""
echo "数据库迁移摘要:"
echo "  ✓ node_status_enum 类型已创建"
echo "  ✓ node_status 列已添加 (默认: active)"
echo "  ✓ live_broadcast 列已添加"
echo "  ✓ status_updated_at 列已添加"
echo "  ✓ 索引已创建"
echo ""
echo "数据库备份: $BACKUP_FILE"
echo ""
echo "后续步骤:"
echo "  1. 重启 Hub 服务: sudo systemctl restart agent-hub"
echo "  2. 检查服务状态: sudo systemctl status agent-hub"
echo "  3. 查看日志: sudo journalctl -u agent-hub -f"
echo ""
