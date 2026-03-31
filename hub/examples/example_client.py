"""
示例客户端：展示如何使用 Agent Hub SDK

这是一个完整的示例，展示：
1. 启动本地 Agent
2. 发布名片到 Hub
3. 搜索匹配的 Agent
4. 处理 P2P 任务请求
"""
import asyncio
from agent_hub_client import HubConnector, WebhookServer
from agent_hub_client.config import LOCAL_WEBHOOK_PORT


# === 定义任务处理函数 ===
async def handle_task(sender_id: str, task_type: str, task_context: dict) -> dict:
    """
    处理来自其他 Agent 的任务请求

    示例：这是一个文本清洗 Agent，接收原始文本并返回清洗后的 Markdown
    """
    print(f"📥 收到任务请求:")
    print(f"   - 发送方: {sender_id}")
    print(f"   - 任务类型: {task_type}")
    print(f"   - 任务上下文: {task_context}")

    # 模拟处理任务
    await asyncio.sleep(1)

    # 返回结果
    result = {
        "status": "completed",
        "result": f"已处理来自 {sender_id} 的 {task_type} 任务",
        "processed_data": "这里是处理后的数据..."
    }

    print(f"✅ 任务处理完成")
    return result


async def main():
    """主函数：完整的 Agent 启动流程"""

    # === 步骤 1: 初始化 HubConnector ===
    connector = HubConnector(
        agent_id="example_text_cleaner_01",
        local_port=LOCAL_WEBHOOK_PORT,
        hub_url="http://localhost:8000"
    )

    # === 步骤 2: 设置并启动 Webhook 服务器 ===
    webhook_server = WebhookServer(port=LOCAL_WEBHOOK_PORT)
    webhook_server.set_task_handler(handle_task)
    webhook_server.run_in_background()
    print(f"🔧 Webhook 服务器已启动")

    # === 步骤 3: 启动 Ngrok 隧道 ===
    from agent_hub_client import NgrokManager
    ngrok = NgrokManager()
    public_url = ngrok.start_tunnel(LOCAL_WEBHOOK_PORT)
    print(f"🔗 Ngrok 隧道已启动: {public_url}")

    # === 步骤 4: 发布名片到 Hub ===
    identity_description = """
    # 文本清洗专家

    ## 提供能力
    - 专注文本清洗与格式化
    - 支持 Markdown 双链语法
    - 处理 K-12 英文阅读资料

    ## 寻求合作
    - 需要原始文本数据源
    """

    success = await connector.publish(
        domain="education",
        intent_type="bid",
        contact_endpoint=f"{public_url}/api/webhook",
        description=identity_description
    )

    if not success:
        print("❌ 发布名片失败，退出")
        return

    print("✅ 名片已发布到 Hub")

    # === 步骤 5: 搜索匹配的 Agent (可选) ===
    print("\n🔍 搜索匹配的 Agent...")
    matches = await connector.search(
        query="需要清洗的原始文本数据",
        domain="education"
    )

    if matches:
        print(f"🎉 找到 {len(matches)} 个匹配:")
        for idx, match in enumerate(matches, 1):
            print(f"   [{idx}] {match['agent_id']} (贡献: {match['tasks_provided']})")
    else:
        print("⚠️ 没有找到匹配的 Agent")

    # === 步骤 6: 保持运行 ===
    print("\n🟢 Agent 正在运行，按 Ctrl+C 退出...")
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\n👋 正在关闭...")

    # 清理
    await connector.close()
    ngrok.stop_tunnel()


if __name__ == "__main__":
    print("=" * 60)
    print("Agent Universal Hub - 示例客户端")
    print("=" * 60)
    asyncio.run(main())
