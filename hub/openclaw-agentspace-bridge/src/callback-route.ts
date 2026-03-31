/**
 * AgentSpace Callback Route for OpenClaw
 *
 * V1.6 特性：
 * - Zero I/O：不读文件，只传路径指针
 * - Promise 修复：await getToken() 确保真实 Token
 * - HITL 人机确认：用户回复"是/否"后才唤醒大模型
 */

import { Hono } from "hono";
import fetch from "node-fetch";
import {
  DeliveryNotification,
  savePendingConfirmation,
  getPendingConfirmation,
  clearPendingConfirmation,
} from "./pending-store";

export interface MessagingChannel {
  sendMessage: (userId: string, message: string) => Promise<void>;
}

export interface Agent {
  resume: (opts: { prompt: string }) => Promise<void>;
}

/**
 * Python 端删除 TaskCache 的回调
 */
async function notifyPythonCleanup(demandId: string, token: string) {
  try {
    await fetch(`http://127.0.0.1:8000/api/local/demand/${demandId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {}
}

/**
 * 创建 AgentSpace 回调路由
 *
 * ⚠️ 移除未使用的 getToken 参数
 */
export function createAgentSpaceCallbackRoute(
  messagingChannel: MessagingChannel,
  agent: Agent
) {
  const app = new Hono();

  app.post("/api/agentspace/callback", async (c) => {
    const notification = await c.req.json<DeliveryNotification>();
    const userId = notification.user_id;

    // 通道二：过期通知
    if (notification.type === "demand_expired") {
      await messagingChannel.sendMessage(
        userId,
        notification.message || "需求已过期，未找到数据。"
      );
      return c.json({ status: "expired" });
    }

    // 通道一：数据送达
    await savePendingConfirmation(userId, notification);

    await messagingChannel.sendMessage(
      userId,
      `🎉 叮咚！好消息来啦！\n` +
        `您之前心心念念的资料，情报网已经帮您弄到手啦！✨\n` +
        `📂 文件位置：${notification.file_path}\n\n` +
        `有了这份资料，您是否需要我马上为您重新执行任务：【${notification.original_task}】？\n` +
        `👉 (回复 "是" 让我开干，或回复 "否" 暂时搁置)`
    );

    return c.json({ status: "received" });
  });

  return app;
}

/**
 * 处理用户确认消息
 *
 * ⚠️ 修复 Promise 逃逸：getToken 支持异步
 */
export async function handleUserConfirmation(
  userId: string,
  message: string,
  messagingChannel: MessagingChannel,
  agent: Agent,
  getToken: () => Promise<string> | string // ✅ 支持异步
): Promise<boolean> {
  const notification = await getPendingConfirmation(userId);
  if (!notification) return false;

  const lowerMsg = message.toLowerCase();

  // 用户同意 - Zero I/O：不读文件，只传路径指针
  if (
    message.includes("是") ||
    lowerMsg === "y" ||
    message.includes("需要") ||
    message.includes("做")
  ) {
    await messagingChannel.sendMessage(
      userId,
      "收到！马上为您注入最新资料，火力全开！🚀"
    );

    await clearPendingConfirmation(userId);

    // ✅ 关键修复：必须 await 获取真实 Token 字符串
    const token = await getToken();
    await notifyPythonCleanup(notification.demand_id, token);

    // ✅ 极简唤醒：只传递路径指针，大模型自己用工具读取
    await agent.resume({
      prompt:
        `【系统情报已送达】\n` +
        `您之前缺失的数据文件已安全下载至本地。\n` +
        `📂 文件绝对路径：${notification.file_path}\n\n` +
        `【系统指令】：请立刻调用你的本地文件分析工具（如代码解释器、文档读取器等）读取上述路径的文件内容，并基于该数据重新执行任务：【${notification.original_task}】`,
    });
    return true;
  }

  // 用户拒绝
  if (
    message.includes("否") ||
    lowerMsg === "n" ||
    message.includes("不用") ||
    message.includes("算")
  ) {
    await clearPendingConfirmation(userId);

    // ✅ 关键修复：必须 await
    const token = await getToken();
    await notifyPythonCleanup(notification.demand_id, token);

    await messagingChannel.sendMessage(
      userId,
      "没问题👌！资料已妥善存好，随时可用~"
    );
    return true;
  }

  return false;
}
