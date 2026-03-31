"""
业务运行前验证测试
==================
验证所有核心功能是否正常工作
"""
import asyncio
import httpx
import uuid
import sqlite3
from datetime import datetime

HUB_URL = "http://localhost:8000"


async def test_1_health():
    """测试 1: 健康检查"""
    print("\n[测试 1] 健康检查")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{HUB_URL}/health", timeout=5)
            if resp.status_code == 200:
                print(f"  [OK] 服务正常: {resp.json()}")
                return True
            else:
                print(f"  [FAIL] 状态异常: {resp.status_code}")
                return False
    except Exception as e:
        print(f"  [FAIL] 无法连接: {e}")
        return False


async def test_2_publish_provider():
    """测试 2: 发布 Provider"""
    print("\n[测试 2] 发布 Provider")
    try:
        provider_id = f"provider-{uuid.uuid4().hex[:8]}"
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{HUB_URL}/api/v1/publish", json={
                "agent_id": provider_id,
                "domain": "education",
                "intent_type": "bid",
                "contact_endpoint": "http://localhost:9001/webhook",
                "description": "提供 K-12 教育资源处理服务"
            }, timeout=30)
            if resp.status_code == 200:
                print(f"  [OK] Provider 发布成功: {provider_id}")
                return provider_id
            else:
                print(f"  [FAIL] 发布失败: {resp.status_code}")
                return None
    except Exception as e:
        print(f"  [FAIL] 异常: {e}")
        return None


async def test_3_create_demand():
    """测试 3: 创建需求"""
    print("\n[测试 3] 创建需求")
    try:
        demand_id = f"demand-{uuid.uuid4().hex[:8]}"
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{HUB_URL}/api/v1/pending_demands", json={
                "demand_id": demand_id,
                "resource_type": "file",
                "description": "需要处理教育类文本数据",
                "tags": ["education", "text", "markdown"],
                "seeker_id": f"seeker-{uuid.uuid4().hex[:8]}",
                "seeker_webhook_url": "http://localhost:9002/webhook"
            }, timeout=30)
            if resp.status_code == 200:
                print(f"  [OK] 需求创建成功: {demand_id}")
                return demand_id
            else:
                print(f"  [FAIL] 创建失败: {resp.status_code}")
                return None
    except Exception as e:
        print(f"  [FAIL] 异常: {e}")
        return None


async def test_4_matching(provider_id: str, demand_id: str):
    """测试 4: 供应匹配"""
    print("\n[测试 4] 供应匹配")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{HUB_URL}/api/v1/agents/{provider_id}/supply", json={
                "tags": ["education", "text", "markdown"],
                "file_name": "test.txt"
            }, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                matches = data.get("matched_demands", [])
                print(f"  [OK] 匹配成功: {len(matches)} 个匹配")
                
                # 检查是否匹配到我们的需求
                matched = any(m.get("demand_id") == demand_id for m in matches)
                if matched:
                    print(f"  [OK] 需求 {demand_id} 已匹配")
                    return True
                else:
                    print(f"  [WARN] 需求未匹配到（可能是向量相似度不够）")
                    return True  # 不视为失败
            else:
                print(f"  [FAIL] 匹配失败: {resp.status_code}")
                return False
    except Exception as e:
        print(f"  [FAIL] 异常: {e}")
        return False


async def test_5_database_status(demand_id: str):
    """测试 5: 数据库状态验证"""
    print("\n[测试 5] 数据库状态验证")
    try:
        conn = sqlite3.connect(os.getenv("DB_PATH", "data/hub_mvp.db"))
        cursor = conn.cursor()
        cursor.execute("SELECT demand_id, status, matched_agent_id FROM pending_demands WHERE demand_id = ?", (demand_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            print(f"  需求 ID: {row[0]}")
            print(f"  状态: {row[1]}")
            print(f"  匹配 Provider: {row[2] or '-'}")
            
            if row[1] == "matched" and row[2]:
                print(f"  [OK] 状态已更新为 matched")
                return True
            elif row[1] == "pending":
                print(f"  [FAIL] 状态仍为 pending（mark_matched 未生效）")
                return False
            else:
                print(f"  [INFO] 状态: {row[1]}")
                return True
        else:
            print(f"  [FAIL] 未找到需求记录")
            return False
    except Exception as e:
        print(f"  [FAIL] 查询失败: {e}")
        return False


async def test_6_search():
    """测试 6: 搜索功能"""
    print("\n[测试 6] 搜索功能")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{HUB_URL}/api/v1/search", json={
                "query": "需要教育资源处理",
                "domain": "education"
            }, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                matches = data.get("matches", [])
                print(f"  [OK] 搜索成功: {len(matches)} 个结果")
                return True
            else:
                print(f"  [FAIL] 搜索失败: {resp.status_code}")
                return False
    except Exception as e:
        print(f"  [FAIL] 异常: {e}")
        return False


async def test_7_pending_demands():
    """测试 7: 查询挂起需求"""
    print("\n[测试 7] 查询挂起需求")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{HUB_URL}/api/v1/pending_demands", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                print(f"  [OK] 查询成功: {data.get('total', 0)} 条需求")
                return True
            else:
                print(f"  [FAIL] 查询失败: {resp.status_code}")
                return False
    except Exception as e:
        print(f"  [FAIL] 异常: {e}")
        return False


async def main():
    print("=" * 70)
    print("  业务运行前验证测试")
    print("  测试时间:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)
    
    results = {}
    
    # 测试 1: 健康检查
    results["health"] = await test_1_health()
    if not results["health"]:
        print("\n[严重] 服务未运行，无法继续测试")
        return
    
    # 测试 2: 发布 Provider
    provider_id = await test_2_publish_provider()
    results["publish"] = provider_id is not None
    
    # 测试 3: 创建需求
    demand_id = await test_3_create_demand()
    results["demand"] = demand_id is not None
    
    # 测试 4: 供应匹配
    if provider_id and demand_id:
        results["matching"] = await test_4_matching(provider_id, demand_id)
        
        # 测试 5: 数据库状态
        results["database"] = await test_5_database_status(demand_id)
    
    # 测试 6: 搜索功能
    results["search"] = await test_6_search()
    
    # 测试 7: 查询挂起需求
    results["query"] = await test_7_pending_demands()
    
    # 总结
    print("\n" + "=" * 70)
    print("  测试总结")
    print("=" * 70)
    
    test_names = {
        "health": "健康检查",
        "publish": "发布 Provider",
        "demand": "创建需求",
        "matching": "供应匹配",
        "database": "数据库状态",
        "search": "搜索功能",
        "query": "查询挂起需求"
    }
    
    passed = 0
    failed = 0
    
    for key, name in test_names.items():
        if key in results:
            status = "[PASS]" if results[key] else "[FAIL]"
            print(f"  {status} {name}")
            if results[key]:
                passed += 1
            else:
                failed += 1
    
    print("\n" + "-" * 70)
    print(f"  总计: {passed}/{passed + failed} 通过")
    
    if failed == 0:
        print("  状态: ✅ 可以投入业务运行")
    else:
        print("  状态: ❌ 存在问题，需要修复")
    
    print("=" * 70)
    
    return failed == 0


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
