"""
Hub 供需匹配状态查询工具
========================
查询 Hub 数据库中的供需匹配状态
"""
import sqlite3
import json
import httpx
from datetime import datetime
from tabulate import tabulate

HUB_URL = "http://localhost:8000"
DB_PATH = os.getenv("DB_PATH", "data/hub_mvp.db")


def query_database():
    """直接查询 SQLite 数据库"""
    print("\n" + "=" * 70)
    print("  [1] 数据库直接查询")
    print("=" * 70)

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 状态统计
        cursor.execute('''
            SELECT status, COUNT(*) as count 
            FROM pending_demands 
            GROUP BY status
        ''')
        stats = cursor.fetchall()

        print("\n[需求状态统计]")
        if stats:
            table_data = []
            total = 0
            for status, count in stats:
                table_data.append([status, count])
                total += count
            table_data.append(["总计", total])
            print(tabulate(table_data, headers=["状态", "数量"], tablefmt="grid"))
        else:
            print("  暂无需求记录")

        # 详细列表
        cursor.execute('''
            SELECT demand_id, resource_type, description, tags, seeker_id, 
                   seeker_webhook_url, created_at, status, matched_agent_id
            FROM pending_demands
            ORDER BY created_at DESC
            LIMIT 50
        ''')
        demands = cursor.fetchall()

        if demands:
            print("\n[需求详情列表]")
            table_data = []
            for d in demands:
                demand_id, resource_type, description, tags, seeker_id, webhook, created_at, status, matched_agent = d
                table_data.append([
                    demand_id[:20] + "..." if len(demand_id) > 20 else demand_id,
                    resource_type,
                    description[:30] + "..." if len(description) > 30 else description,
                    status,
                    matched_agent or "-"
                ])
            print(tabulate(
                table_data, 
                headers=["ID", "类型", "描述", "状态", "匹配Provider"],
                tablefmt="grid"
            ))

        conn.close()

    except Exception as e:
        print(f"查询失败: {e}")


def query_api():
    """通过 API 查询"""
    print("\n" + "=" * 70)
    print("  [2] API 接口查询")
    print("=" * 70)

    try:
        with httpx.Client(timeout=10.0) as client:
            # 健康检查
            resp = client.get(f"{HUB_URL}/health")
            print(f"\n[Hub 健康状态]")
            print(f"  状态: {resp.status_code}")
            print(f"  响应: {resp.json()}")

            # 查询挂起需求
            resp = client.get(f"{HUB_URL}/api/v1/pending_demands")
            if resp.status_code == 200:
                data = resp.json()
                print(f"\n[挂起需求 API 查询]")
                print(f"  总数: {data.get('total')}")

                demands = data.get("demands", [])
                if demands:
                    table_data = []
                    for d in demands:
                        table_data.append([
                            d.get("demand_id", "")[:20],
                            d.get("resource_type", ""),
                            d.get("description", "")[:30],
                            d.get("status", ""),
                            d.get("seeker_id", "")[:15]
                        ])
                    print(tabulate(
                        table_data,
                        headers=["ID", "类型", "描述", "状态", "Seeker"],
                        tablefmt="grid"
                    ))
            else:
                print(f"  查询失败: {resp.status_code}")

    except Exception as e:
        print(f"API 查询失败: {e}")


def query_matched_for_provider(provider_id: str = None):
    """查询 Provider 的已匹配订单"""
    print("\n" + "=" * 70)
    print("  [3] Provider 已匹配订单查询")
    print("=" * 70)

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if provider_id:
            cursor.execute('''
                SELECT demand_id, resource_type, description, seeker_id, 
                       seeker_webhook_url, created_at, status
                FROM pending_demands
                WHERE matched_agent_id = ? AND status = 'matched'
            ''', (provider_id,))
        else:
            cursor.execute('''
                SELECT demand_id, resource_type, description, seeker_id, 
                       seeker_webhook_url, created_at, matched_agent_id
                FROM pending_demands
                WHERE status = 'matched'
            ''')

        matched = cursor.fetchall()

        if matched:
            print(f"\n[已匹配待发货订单] ({len(matched)} 条)")
            table_data = []
            for m in matched:
                table_data.append([
                    m[0][:20],
                    m[1],
                    m[2][:30],
                    m[3][:15] if m[3] else "-",
                    m[6] if len(m) > 6 else provider_id
                ])
            print(tabulate(
                table_data,
                headers=["需求ID", "类型", "描述", "Seeker", "Provider"],
                tablefmt="grid"
            ))
        else:
            print("\n  暂无已匹配订单")

        conn.close()

    except Exception as e:
        print(f"查询失败: {e}")


def main():
    print("\n" + "=" * 70)
    print("  Hub 供需匹配状态查询工具")
    print("  查询时间:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)

    query_database()
    query_api()
    query_matched_for_provider()

    print("\n" + "=" * 70)
    print("  查询完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
