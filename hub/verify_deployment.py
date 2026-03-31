"""
验证服务器部署状态
"""
import httpx
import sys

def verify_server(url=None):
    print("=" * 60)
    print(f"验证服务器部署: {url}")
    print("=" * 60)
    
    all_passed = True
    
    # 1. 健康检查
    print("\n【1】健康检查")
    try:
        r = httpx.get(f"{url}/health", timeout=10)
        if r.status_code == 200:
            data = r.json()
            print(f"  ✅ 服务正常运行")
            print(f"     状态: {data.get('status')}")
            print(f"     版本: {data.get('version')}")
        else:
            print(f"  ❌ 健康检查失败: {r.status_code}")
            all_passed = False
    except Exception as e:
        print(f"  ❌ 连接失败: {e}")
        all_passed = False
    
    # 2. 测试 Embedding 功能（通过发布接口）
    print("\n【2】测试 Embedding 功能")
    try:
        publish_data = {
            "agent_id": "test-verify-001",
            "domain": "test",
            "intent_type": "bid",
            "contact_endpoint": "http://localhost:9001",
            "description": "我是一个AI助手，擅长Python编程"
        }
        
        r = httpx.post(
            f"{url}/api/v1/publish",
            json=publish_data,
            timeout=60
        )
        
        if r.status_code == 200:
            data = r.json()
            print(f"  ✅ Embedding 功能正常")
            print(f"     Agent ID: {data.get('agent_id')}")
            print(f"     状态: {data.get('status')}")
        elif r.status_code == 500:
            print(f"  ❌ Embedding 失败 (500)")
            print(f"     响应: {r.text}")
            all_passed = False
        else:
            print(f"  ⚠️  返回状态: {r.status_code}")
            print(f"     响应: {r.text}")
            
    except httpx.TimeoutException:
        print(f"  ⏱️  请求超时（可能 Embedding API 较慢）")
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        all_passed = False
    
    # 3. 测试搜索功能
    print("\n【3】测试搜索功能")
    try:
        search_data = {
            "query": "Python编程",
            "domain": "test",
            "top_k": 3
        }
        
        r = httpx.post(
            f"{url}/api/v1/search",
            json=search_data,
            timeout=60
        )
        
        if r.status_code == 200:
            data = r.json()
            matches = data.get("matches", [])
            print(f"  ✅ 搜索功能正常")
            print(f"     找到 {len(matches)} 个匹配")
            for i, match in enumerate(matches[:2], 1):
                print(f"     {i}. {match.get('agent_id')}")
        else:
            print(f"  ❌ 搜索失败: {r.status_code}")
            print(f"     响应: {r.text}")
            all_passed = False
            
    except httpx.TimeoutException:
        print(f"  ⏱️  请求超时")
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        all_passed = False
    
    # 4. 检查 API 文档
    print("\n【4】检查 API 文档")
    try:
        r = httpx.get(f"{url}/docs", timeout=10)
        if r.status_code == 200:
            print(f"  ✅ API 文档可访问")
            print(f"     地址: {url}/docs")
        else:
            print(f"  ⚠️  API 文档返回: {r.status_code}")
    except Exception as e:
        print(f"  ❌ 无法访问 API 文档: {e}")
    
    # 总结
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 所有检查通过！部署成功！")
    else:
        print("❌ 部分检查失败，请查看日志")
    print("=" * 60)
    
    return all_passed

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else os.getenv("HUB_URL", "http://localhost:8000")
    verify_server(url)
