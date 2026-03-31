/**
 * Pending Confirmation Store for OpenClaw-ClawHub Bridge
 *
 * V1.6 特性：
 * - 互斥锁队列：防止异步并发写覆盖
 * - 数组队列：单用户多任务 FIFO 处理
 * - 读取也加锁：彻底杜绝脏读 (Dirty Read)
 * - 持久化存储：Node.js 重启后状态恢复
 */

import { promises as fsPromises } from "fs";
import path from "path";

export interface DeliveryNotification {
  type: "resource_delivery" | "demand_expired";
  demand_id: string;
  file_path?: string;
  provider_id?: string;
  resource_type?: string;
  user_id: string;
  original_task: string;
  message?: string;
  timestamp: string;
}

const PENDING_DIR = path.join(
  process.env.HOME || process.env.USERPROFILE || "",
  ".clawhub",
  "pending_confirmations"
);

// ⚠️ 内存互斥锁队列：防止异步并发写覆盖
const _writeLocks = new Map<string, Promise<void>>();

async function runWithLock<T>(userId: string, task: () => Promise<T>): Promise<T> {
  const previousLock = _writeLocks.get(userId) || Promise.resolve();

  const nextLock = previousLock.catch(() => {}).then(task);
  _writeLocks.set(userId, nextLock as Promise<void>);

  try {
    return await nextLock;
  } finally {
    if (_writeLocks.get(userId) === nextLock) {
      _writeLocks.delete(userId); // 防止内存泄漏
    }
  }
}

async function ensureDir() {
  try {
    await fsPromises.mkdir(PENDING_DIR, { recursive: true });
  } catch {}
}

/**
 * 保存：推入数组队列（带互斥锁）
 */
export async function savePendingConfirmation(
  userId: string,
  notification: DeliveryNotification
): Promise<void> {
  await ensureDir();
  const filePath = path.join(PENDING_DIR, `${userId}.json`);

  await runWithLock(userId, async () => {
    let pending: DeliveryNotification[] = [];
    try {
      pending = JSON.parse(await fsPromises.readFile(filePath, "utf-8"));
    } catch {}

    pending.push(notification);
    await fsPromises.writeFile(filePath, JSON.stringify(pending), "utf-8");
  });
}

/**
 * 读取：获取队列中最老的一个（FIFO + 互斥锁防脏读）
 */
export async function getPendingConfirmation(
  userId: string
): Promise<DeliveryNotification | null> {
  const filePath = path.join(PENDING_DIR, `${userId}.json`);

  // ✅ 终极稳定：将读取也放入互斥锁，彻底杜绝"脏读 (Dirty Read)"
  return await runWithLock(userId, async () => {
    try {
      const pending: DeliveryNotification[] = JSON.parse(
        await fsPromises.readFile(filePath, "utf-8")
      );
      return pending.length > 0 ? pending[0] : null;
    } catch {
      return null;
    }
  });
}

/**
 * 按 demand_id 精准查找（互斥锁防脏读）
 */
export async function getPendingByDemandId(
  userId: string,
  demandId: string
): Promise<DeliveryNotification | null> {
  const filePath = path.join(PENDING_DIR, `${userId}.json`);

  return await runWithLock(userId, async () => {
    try {
      const pending: DeliveryNotification[] = JSON.parse(
        await fsPromises.readFile(filePath, "utf-8")
      );
      return pending.find((n) => n.demand_id === demandId) || null;
    } catch {
      return null;
    }
  });
}

/**
 * 清理：弹出队列第一个（带互斥锁）
 */
export async function clearPendingConfirmation(userId: string): Promise<void> {
  const filePath = path.join(PENDING_DIR, `${userId}.json`);

  await runWithLock(userId, async () => {
    try {
      const pending: DeliveryNotification[] = JSON.parse(
        await fsPromises.readFile(filePath, "utf-8")
      );
      pending.shift();

      if (pending.length > 0) {
        await fsPromises.writeFile(filePath, JSON.stringify(pending), "utf-8");
      } else {
        await fsPromises.unlink(filePath);
      }
    } catch {}
  });
}

/**
 * 按 demand_id 精准删除（带互斥锁）
 */
export async function clearPendingByDemandId(
  userId: string,
  demandId: string
): Promise<void> {
  const filePath = path.join(PENDING_DIR, `${userId}.json`);

  await runWithLock(userId, async () => {
    try {
      let pending: DeliveryNotification[] = JSON.parse(
        await fsPromises.readFile(filePath, "utf-8")
      );
      pending = pending.filter((n) => n.demand_id !== demandId);

      if (pending.length > 0) {
        await fsPromises.writeFile(filePath, JSON.stringify(pending), "utf-8");
      } else {
        await fsPromises.unlink(filePath);
      }
    } catch {}
  });
}

/**
 * 加载所有待确认状态（启动时恢复）
 */
export async function loadAllPendingConfirmations(): Promise<
  Map<string, DeliveryNotification[]>
> {
  const result = new Map<string, DeliveryNotification[]>();
  await ensureDir();
  try {
    for (const file of await fsPromises.readdir(PENDING_DIR)) {
      if (!file.endsWith(".json")) continue;
      const userId = file.replace(".json", "");
      const filePath = path.join(PENDING_DIR, file);
      try {
        const pending: DeliveryNotification[] = JSON.parse(
          await fsPromises.readFile(filePath, "utf-8")
        );
        result.set(userId, pending);
      } catch {}
    }
  } catch {}
  return result;
}
