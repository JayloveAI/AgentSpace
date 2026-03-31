"""
完整诊断脚本 - 在服务器上运行
"""
import os
import sys
sys.path.insert(0, '.')

print("=" * 70)
print("完整诊断")
print("=" * 70)

# 1. 检查 API Key
print("\n1. 检查 API Key 配置:")
from hub_server.config import EMBEDDING_API_KEY, GLM_API_KEY
print(f"   EMBEDDING_API_KEY: {EMBEDDING_API_KEY[:20]}..." if EMBEDDING_API_KEY else "   EMBEDDING_API_KEY: 未设置")
print(f"   GLM_API_KEY: {GLM_API_KEY[:20]}..." if GLM_API_KEY else "   GLM_API_KEY: 未设置")

# 2. 检查 match_service 中的硬编码
print("\n2. 检查 match_service.py 中的硬编码:")
with open('hub_server/services/match_service.py', 'r', encoding='utf-8') as f:
    content = f.read()
    if 'GLM_API_KEY' in content:
        print("   ✅ 包含硬编码 API Key")
    else:
        print("   ❌ 不包含硬编码 API Key")

# 3. 测试 Embedding 服务
print("\n3. 测试 Embedding 服务:")
import httpx
api_key = os.getenv("GLM_API_KEY", "")
try:
    r = httpx.post(
        'https://open.bigmodel.cn/api/paas/v4/embeddings',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        json={
            'model': 'embedding-3',
            'input': '测试'
        },
        timeout=30
    )
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        print("   ✅ API 调用成功")
    else:
        print(f"   ❌ API 调用失败: {r.text[:100]}")
except Exception as e:
    print(f"   ❌ 异常: {e}")

# 4. 测试 EmbeddingService 类
print("\n4. 测试 EmbeddingService 类:")
from hub_server.services.match_service import embedding_service
print(f"   embedding_service.api_key: {embedding_service.api_key[:20]}..." if embedding_service.api_key else "   api_key: 未设置")
print(f"   embedding_service.provider: {embedding_service.provider}")

print("\n" + "=" * 70)
