"""
诊断 Embedding 配置问题
"""
import os
import sys

print("=" * 70)
print("Embedding 配置诊断")
print("=" * 70)

# 1. 检查当前工作目录
print(f"\n1. 当前工作目录: {os.getcwd()}")

# 2. 检查 .env 文件位置
env_files = [
    '.env',
    'hub_server/.env',
    '..\\.env'
]

print("\n2. 检查 .env 文件:")
for env_file in env_files:
    exists = os.path.exists(env_file)
    print(f"   {env_file}: {'存在' if exists else '不存在'}")
    if exists:
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'GLM_API_KEY' in content:
                for line in content.split('\n'):
                    if 'GLM_API_KEY' in line and not line.startswith('#'):
                        print(f"      -> {line[:50]}...")

# 3. 加载配置
print("\n3. 加载配置:")
sys.path.insert(0, '.')

try:
    from dotenv import load_dotenv
    load_dotenv('.env')
    print("   已加载 .env")
except Exception as e:
    print(f"   加载失败: {e}")

# 4. 检查环境变量
print("\n4. 环境变量:")
print(f"   EMBEDDING_PROVIDER: {os.getenv('EMBEDDING_PROVIDER', '未设置')}")
print(f"   GLM_API_KEY: {os.getenv('GLM_API_KEY', '未设置')[:30]}...")
print(f"   GLM_EMBEDDING_MODEL: {os.getenv('GLM_EMBEDDING_MODEL', '未设置')}")

# 5. 直接测试 API
print("\n5. 直接测试 Embedding API:")
import httpx

api_key = os.getenv('GLM_API_KEY', '')
if api_key:
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
            data = r.json()
            print(f"   成功! 向量维度: {len(data['data'][0]['embedding'])}")
        else:
            print(f"   失败: {r.text[:200]}")
    except Exception as e:
        print(f"   异常: {e}")
else:
    print("   API Key 未设置")

print("\n" + "=" * 70)
