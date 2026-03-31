"""
检查环境变量配置
"""
import sys
sys.path.insert(0, '.')

from hub_server.config import EMBEDDING_PROVIDER, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS, EMBEDDING_API_KEY

print("=" * 60)
print("Embedding 配置检查")
print("=" * 60)
print(f"Provider: {EMBEDDING_PROVIDER}")
print(f"Model: {EMBEDDING_MODEL}")
print(f"Dimensions: {EMBEDDING_DIMENSIONS}")
print(f"API Key: {EMBEDDING_API_KEY[:20]}...")
print(f"API Key 长度: {len(EMBEDDING_API_KEY)}")

# 测试直接调用
import httpx

print("\n" + "=" * 60)
print("直接测试 Embedding API")
print("=" * 60)

r = httpx.post(
    'https://open.bigmodel.cn/api/paas/v4/embeddings',
    headers={
        'Authorization': f'Bearer {EMBEDDING_API_KEY}',
        'Content-Type': 'application/json'
    },
    json={
        'model': EMBEDDING_MODEL,
        'input': '测试文本'
    }
)

print(f"Status: {r.status_code}")
print(f"Response: {r.text[:200]}")
