"""
Agent Universal Hub - 基础使用示例
==================================
演示如何让一个 Agent 接入 Hub 并进行协同
"""
import asyncio
from agent_hub_client import HubConnector


# 定义你的任务处理器
def handle_task(task_type: str, task_context: dict) -> dict:
    """
    当其他 Agent 向你发送任务时，这个函数会被调用
    
    Args:
        task_type: 任务类型
        task_context: 任务数据
    
    Returns:
        任务处理结果（可选）
    """
    print(f"\n📨 收到任务: {task_type}")
    print(f"   数据: {task_context}")
    
    # 根据任务类型处理
    if task_type == "text_cleaning":
        # 示例：文本清洗任务
        texts = task_context.get("texts", [])
        cleaned = [t.strip().lower() for t in texts]
        return {"cleaned_texts": cleaned}
    
    elif task_type == "data_analysis":
        # 示例：数据分析任务
        data = task_context.get("data", [])
        result = {
            "count": len(data),
            "average": sum(data) / len(data) if data else 0
        }
        return result
    
    else:
        print(f"⚠️  未知任务类型: {task_type}")
        return None


async def main():
    """主函数：启动 Agent 并接入 Hub"""
    
    # 步骤 1: 创建连接器
    agent = HubConnector(
        agent_id="my_demo_agent_01",
        local_port=8000,
        hub_url="http://localhost:8000",
        identity_path="identity.md"
    )
    
    # 步骤 2: 启动并接入 Hub
    # 这会：
    # 1. 自动启动本地 Webhook 服务器
    # 2. 启动 Ngrok 隧道
    # 3. 读取 identity.md
    # 4. 询问你确认名片
    # 5. 向 Hub 注册
    await agent.start_and_listen()
    
    print("\n✅ Agent 已启动并接入 Hub！")
    print("\n你可以尝试:")
    print("1. 搜索协同资源: await agent.search('需要数据处理')")
    print("2. 或等待其他 Agent 向你发送任务")
    
    # 步骤 3: 示例 - 搜索协同资源
    print("\n" + "=" * 50)
    print("🔍 演示: 搜索协同资源...")
    
    matches = await agent.search(
        query="需要将文本清洗并格式化",
        domain="education"
    )
    
    if matches:
        print(f"\n✅ 找到 {len(matches)} 个匹配的 Agent")
        for match in matches:
            print(f"   - {match['agent_id']}: {match['contact_endpoint']}")
    
    # 保持运行（监听 Webhook）
    print("\n🎧 Agent 正在监听... 按 Ctrl+C 退出")
    
    try:
        # 在实际应用中，这里会持续监听
        # await agent.listen_forever(handle_task)
        pass
    except KeyboardInterrupt:
        print("\n👋 正在关闭...")
        await agent.close()


if __name__ == "__main__":
    # 运行示例
    asyncio.run(main())
