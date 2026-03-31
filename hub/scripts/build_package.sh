#!/bin/bash
#===============================================================================
# AgentHub V1.5 打包脚本
#===============================================================================
# 在本地执行，生成部署包
#===============================================================================

set -e

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

#-------------------------------------------------------------------------------
# 配置
#-------------------------------------------------------------------------------

PACKAGE_NAME="agent-hub-v1.5"
PACKAGE_DIR="dist/${PACKAGE_NAME}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

#-------------------------------------------------------------------------------
# 打包流程
#-------------------------------------------------------------------------------

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AgentHub V1.5 打包${NC}"
echo -e "${BLUE}========================================${NC}\n"

# 1. 清理旧的打包文件
echo "清理旧的打包文件..."
rm -rf dist/

# 2. 创建打包目录
echo "创建打包目录..."
mkdir -p ${PACKAGE_DIR}

# 3. 复制必要文件
echo "复制文件..."

# Hub 服务端
mkdir -p ${PACKAGE_DIR}/hub_server
cp -r hub_server/*.py ${PACKAGE_DIR}/hub_server/
cp -r hub_server/api ${PACKAGE_DIR}/hub_server/
cp -r hub_server/db ${PACKAGE_DIR}/hub_server/
cp -r hub_server/services ${PACKAGE_DIR}/hub_server/

# 客户端 SDK
mkdir -p ${PACKAGE_DIR}/client_sdk
cp -r client_sdk/*.py ${PACKAGE_DIR}/client_sdk/
cp -r client_sdk/cli ${PACKAGE_DIR}/client_sdk/
cp -r client_sdk/core ${PACKAGE_DIR}/client_sdk/
cp -r client_sdk/daemon ${PACKAGE_DIR}/client_sdk/
cp -r client_sdk/tunnel ${PACKAGE_DIR}/client_sdk/
cp -r client_sdk/webhook ${PACKAGE_DIR}/client_sdk/

# 测试文件
mkdir -p ${PACKAGE_DIR}/tests
cp tests/*.py ${PACKAGE_DIR}/tests/ 2>/dev/null || true
mkdir -p ${PACKAGE_DIR}/tests/fixtures

# 脚本
mkdir -p ${PACKAGE_DIR}/scripts
cp scripts/*.sh ${PACKAGE_DIR}/scripts/ 2>/dev/null || true

# 配置文件
cp requirements.txt ${PACKAGE_DIR}/
cp .env.example ${PACKAGE_DIR}/ 2>/dev/null || true
cp README.md ${PACKAGE_DIR}/

# 4. 生成版本信息
cat > ${PACKAGE_DIR}/VERSION << EOF
AgentHub V1.5
Build Time: ${TIMESTAMP}
Git Commit: $(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
EOF

# 5. 创建部署说明
cat > ${PACKAGE_DIR}/DEPLOY.txt << EOF
AgentHub V1.5 部署说明
======================

快速部署:
  bash scripts/deploy_to_cloud.sh <server_ip>

数据库迁移:
  psql -U agenthub -d agent_hub -f hub_server/db/migrations/002_add_live_status.sql

启动服务:
  uvicorn hub_server.main:app --host 0.0.0.0 --port 8000

API 文档:
  http://localhost:8000/docs
EOF

echo -e "${GREEN}✓ 打包完成: ${PACKAGE_DIR}${NC}"
echo ""
echo "部署包内容:"
ls -lh ${PACKAGE_DIR}/

# 6. (可选) 创建压缩包
read -p "是否创建压缩包? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    cd dist
    tar -czf ${PACKAGE_NAME}_${TIMESTAMP}.tar.gz ${PACKAGE_NAME}
    echo -e "${GREEN}✓ 压缩包创建完成: ${PACKAGE_NAME}_${TIMESTAMP}.tar.gz${NC}"
fi
