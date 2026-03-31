"""
自动大文件处理示例
===================
演示 AgentHub V1.5 的 Payload 自动处理功能

场景：当需要传输大文件时，系统自动：
1. 检测文件大小
2. 超过阈值自动上传到外部存储
3. 生成访问链接
4. 接收方自动下载还原
"""

import asyncio
from client_sdk.core.payload_handler import (
    PayloadHandler,
    prepare_outbound_payload,
    restore_inbound_payload,
    auto_handle_payload
)


# ============================================================================
# 示例 1: 基本使用
# ============================================================================

async def example_basic():
    """基本用法：手动处理大文件"""
    print("=" * 60)
    print("示例 1: 基本 Payload 处理")
    print("=" * 60)

    # 原始 payload - 包含大数组
    original_payload = {
        "task_type": "process_large_dataset",
        "task_context": {
            "format": "json",
            "data": list(range(10000)),  # 大数据集
            "metadata": {
                "source": "sensor_data",
                "timestamp": "2026-03-13"
            }
        }
    }

    # 计算原始大小
    import json
    original_size = len(json.dumps(original_payload).encode('utf-8'))
    print(f"原始 Payload 大小: {original_size:,} 字节 ({original_size/1024:.2f} KB)")

    # 发送方：准备 payload（自动处理大文件）
    processed = prepare_outbound_payload(original_payload)
    print(f"\n处理后结构:")
    if "data_links" in processed:
        print(f"  - 大字段数量: {len(processed['data_links'])}")
        for link in processed['data_links']:
            print(f"    * {link['field']}: {link['url']}")
    print(f"  - 小字段保留: {list(processed.get('small_data', {}).keys())}")

    # 接收方：还原 payload（自动下载大文件）
    restored = restore_inbound_payload(processed)
    print(f"\n还原后数据匹配: {restored == original_payload}")


# ============================================================================
# 示例 2: 自定义阈值
# ============================================================================

async def example_custom_threshold():
    """自定义大小阈值"""
    print("\n" + "=" * 60)
    print("示例 2: 自定义大小阈值")
    print("=" * 60)

    # 创建自定义处理器 (50KB 阈值)
    handler = PayloadHandler(size_threshold=1024 * 50)

    payload = {
        "task_type": "text_analysis",
        "task_context": {
            "text": "Hello World " * 1000  # 约 13KB
        }
    }

    # 检查大小
    import json
    size = len(json.dumps(payload).encode('utf-8'))
    print(f"Payload 大小: {size/1024:.2f} KB")

    processed = handler.prepare_payload(payload)
    if "data_links" in processed:
        print("✓ 检测到大字段，已转换为外部链接")
    else:
        print("✓ Payload 小于阈值，直接传输")


# ============================================================================
# 示例 3: Agent 任务处理器自动处理
# ============================================================================

@auto_handle_payload(size_threshold=1024 * 100)  # 100KB
async def my_agent_task_handler(task_type: str, task_context: dict):
    """
    Agent 任务处理器 - 使用装饰器自动处理大文件

    收到的消息会自动还原 data_links，无需手动处理
    """
    print(f"\n处理任务: {task_type}")

    # task_context 已自动还原，可以直接使用
    large_data = task_context.get("data", [])
    print(f"收到数据量: {len(large_data)} 条")

    # 处理数据...
    return {
        "status": "success",
        "processed": len(large_data)
    }


async def example_decorator():
    """使用装饰器自动处理"""
    print("\n" + "=" * 60)
    print("示例 3: 使用装饰器自动处理")
    print("=" * 60)

    # 模拟收到的消息（包含 data_links）
    received_message = {
        "task_type": "process_data",
        "_metadata": {"compressed": True},
        "data_links": [
            {
                "field": "data",
                "url": "data:application/json;base64,W29iamVjdCBPYmplY3Rd"  # Base64 示例
            }
        ],
        "small_data": {
            "format": "json"
        }
    }

    # 调用处理器（装饰器会自动还原）
    result = await my_agent_task_handler(
        "process_data",
        received_message
    )
    print(f"处理结果: {result}")


# ============================================================================
# 示例 4: 完整的 Agent 通信流程
# ============================================================================

async def example_full_flow():
    """完整的 Agent A -> Agent B 通信流程"""
    print("\n" + "=" * 60)
    print("示例 4: 完整的 Agent 通信流程")
    print("=" * 60)

    # === Agent A: 发送方 ===
    print("\n[Agent A] 准备发送任务...")

    agent_a_payload = {
        "task_type": "analyze_logs",
        "task_context": {
            "log_file": ["ERROR: ..."] * 5000,  # 大日志文件
            "analysis_type": "pattern_matching"
        }
    }

    # 自动处理大文件
    outgoing = prepare_outbound_payload(agent_a_payload)
    print(f"[Agent A] Payload 已准备:")
    if "data_links" in outgoing:
        print(f"  - 大文件已上传: {len(outgoing['data_links'])} 个")
        print(f"  - 传输大小: ~1KB (仅元数据)")

    # === Agent B: 接收方 ===
    print("\n[Agent B] 收到任务，自动还原...")

    @auto_handle_payload()
    async def agent_b_handler(task_type: str, task_context: dict):
        # task_context 已自动还原
        log_count = len(task_context.get("log_file", []))
        print(f"[Agent B] 收到 {log_count} 条日志")
        return {"status": "done", "analyzed": log_count}

    result = await agent_b_handler(
        outgoing.get("small_data", {}).get("task_type", "analyze_logs"),
        outgoing
    )
    print(f"[Agent B] 处理完成: {result}")


# ============================================================================
# 示例 5: 多种存储提供商
# ============================================================================

async def example_storage_providers():
    """不同的外部存储选项"""
    print("\n" + "=" * 60)
    print("示例 5: 外部存储选项")
    print("=" * 60)

    providers = {
        "temp": "临时文件服务 (temp.sh) - 无需配置",
        "s3": "AWS S3 - 需要 boto3 + AWS 凭证",
        "oss": "阿里云 OSS - 需要 oss2 + 凭证",
        "local": "本地 MinIO - 需要本地服务",
        "inline": "Base64 编码 - 直接内联 (不推荐大文件)"
    }

    for provider, description in providers.items():
        print(f"  {provider:10} - {description}")

    # 使用临时文件服务 (最简单)
    handler = PayloadHandler(
        storage_provider="temp",
        size_threshold=1024  # 1KB 阈值用于演示
    )

    test_payload = {"data": "x" * 2000}  # 超过阈值
    processed = handler.prepare_payload(test_payload)
    print(f"\n使用 temp.sh 存储:")
    if "data_links" in processed:
        print(f"  URL: {processed['data_links'][0]['url']}")


# ============================================================================
# 主函数
# ============================================================================

async def main():
    """运行所有示例"""
    await example_basic()
    await example_custom_threshold()
    await example_decorator()
    await example_full_flow()
    await example_storage_providers()

    print("\n" + "=" * 60)
    print("所有示例完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
