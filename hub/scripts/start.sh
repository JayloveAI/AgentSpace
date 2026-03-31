#!/bin/bash
# Agent Universal Hub 快速启动脚本

set -e

echo "🚀 Agent Universal Hub - 快速启动"
echo "=================================="
echo ""

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ 错误: 未安装 Docker"
    echo "   请先安装 Docker: https://www.docker.com/get-started"
    exit 1
fi

# 检查 docker-compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ 错误: 未安装 docker-compose"
    echo "   请先安装 docker-compose: https://docs.docker.com/compose/install/"
    exit 1
fi

# 复制环境变量模板
if [ ! -f .env ]; then
    echo "📄 创建 .env 文件..."
    cp .env.example .env
    echo "⚠️  请编辑 .env 文件，设置你的 OpenAI API Key"
    echo ""
fi

# 启动服务
echo "🐳 启动 Docker 服务..."
docker-compose up -d

echo ""
echo "✅ 服务已启动！"
echo ""
echo "📍 访问地址:"
echo "   - Hub API:     http://localhost:8000"
echo "   - API 文档:    http://localhost:8000/docs"
echo "   - PostgreSQL:  localhost:5432"
echo ""
echo "📊 查看日志: docker-compose logs -f"
echo "🛑 停止服务: docker-compose down"
