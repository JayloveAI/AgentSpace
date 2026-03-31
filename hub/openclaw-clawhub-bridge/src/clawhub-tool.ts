/**
 * ClawHub Outsource Tool for OpenClaw
 *
 * 当大模型发现本地缺少某份核心数据时，调用此工具向全网发起异步外包求助。
 *
 * V1.6 特性：
 * - 实时异步读取 Token（无缓存，确保与 Python 端同步）
 * - 支持 user_id 透传
 * - 高情商话术建议
 */

import { z } from "zod";
import { promises as fsPromises } from "fs";
import path from "path";
import fetch from "node-fetch";

// ⚠️ 移除缓存：每次实时读取，确保与 Python 端同步
// ❌ 删掉 let cachedToken: string | null = null;

async function getLocalTokenAsync(): Promise<string> {
  const tokenPath = path.join(
    process.env.HOME || process.env.USERPROFILE || "",
    ".clawhub",
    ".local_token"
  );
  try {
    // ✅ 每次异步读取，0.1ms 级别，不阻塞事件循环
    const data = await fsPromises.readFile(tokenPath, "utf-8");
    return data.trim();
  } catch {
    return "";
  }
}

export const ClawHubOutsourceSchema = z.object({
  missing_data_description: z.string().describe("详细描述缺失的数据"),
  original_task: z.string().describe("你当前正在处理的总任务目标"),
  resource_type: z.string().optional().describe("资源类型，如 csv, pdf, json"),
});

export interface ClawHubToolConfig {
  getUserId: () => string;
}

export function createClawHubOutsourceTool(config: ClawHubToolConfig) {
  return {
    name: "clawhub_request_data",
    description:
      "【终极数据获取与兜底工具】\n" +
      "当你遇到以下情况时必须调用此工具：\n" +
      "1. 系统底层抛出强制降级指令（如遇到 401/403 错误或付费墙）。\n" +
      "2. 【软失败兜底】：公开网页虽然能打开，但缺乏实质性的深度数据，或找不到用户需要的核心文件。\n" +
      "调用此工具可将需求发布至全球 P2P 异步外包网络，由其他高权限节点代为获取。",

    schema: ClawHubOutsourceSchema,

    async execute(input: z.infer<typeof ClawHubOutsourceSchema>) {
      const token = await getLocalTokenAsync();
      if (!token) return "❌ ClawHub 未启动或 Token 文件不存在。";

      try {
        const response = await fetch("http://127.0.0.1:8000/api/local/trigger_demand", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`,
          },
          body: JSON.stringify({
            description: input.missing_data_description,
            original_task: input.original_task,
            resource_type: input.resource_type || "resource",
            user_id: config.getUserId(),
          }),
        });

        if (!response.ok) return `❌ 调用失败: ${response.status}`;

        const result = (await response.json()) as { demand_id: string };
        return (
          `✅ 数据需求已成功提交至 ClawHub 异步外包网络 (需求 ID: ${result.demand_id})。\n` +
          `系统底层正在全力进行全网匹配与资料获取。\n\n` +
          `【状态与建议】：\n` +
          `1. 状态：资料获取完全异步，送达后将通过独立通道通知。\n` +
          `2. 情绪建议：向用户汇报时，可用抱歉但热情的语气安抚。\n` +
          `3. 话术风格参考："太抱歉啦，我刚好缺了这份数据 🥺 不过别担心！我已经派出情报网去全网搜寻了！"\n` +
          `[系统报告完毕]`
        );
      } catch (error) {
        return `❌ 网络错误: ${(error as Error).message}`;
      }
    },
  };
}

// 导出 getToken 函数供 callback-route 使用
export { getLocalTokenAsync };
