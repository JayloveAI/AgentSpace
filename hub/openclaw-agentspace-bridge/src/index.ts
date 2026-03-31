/**
 * OpenClaw-AgentSpace Bridge
 *
 * 让 OpenClaw (Node.js) 与 AgentSpace (Python) 无缝协作的桥接层
 *
 * V1.6 特性：
 * - 边车模式：Python 守护进程 + Node.js 业务控制
 * - Zero I/O：只传路径指针，不读文件
 * - HITL：人机确认后才唤醒大模型
 * - 互斥锁：异步并发写不覆盖
 * - 实时 Token：每次异步读取，Python 重启无死锁
 */

// Tool
export {
  createAgentSpaceOutsourceTool,
  AgentSpaceOutsourceSchema,
  getLocalTokenAsync,
} from "./agentspace-tool";
export type { AgentSpaceToolConfig } from "./agentspace-tool";

// Pending Store
export {
  savePendingConfirmation,
  getPendingConfirmation,
  getPendingByDemandId,
  clearPendingConfirmation,
  clearPendingByDemandId,
  loadAllPendingConfirmations,
} from "./pending-store";
export type { DeliveryNotification } from "./pending-store";

// Callback Route
export {
  createClawhubCallbackRoute,
  handleUserConfirmation,
} from "./callback-route";
export type { MessagingChannel, Agent } from "./callback-route";
