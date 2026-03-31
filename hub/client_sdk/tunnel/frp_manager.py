"""
FRPManager - FRP 隧道管理器
===========================
替代 Ngrok 的内网穿透方案，使用自建 FRP 服务器
"""
import asyncio
import subprocess
from typing import Optional
from pathlib import Path
import httpx
import time
import hashlib


def get_deterministic_port(agent_id: str, base: int = 8001, range_size: int = 999) -> int:
    """基于 agent_id 计算确定性端口（零网络依赖）"""
    hash_bytes = hashlib.sha256(agent_id.encode()).digest()
    port_offset = int.from_bytes(hash_bytes[:4], 'big') & 0x7FFFFFFF
    return base + (port_offset % range_size)


class FRPManager:
    """
    FRP 隧道管理器

    使用自建的 FRP 服务器进行内网穿透
    优势：
    - 国内访问快速稳定
    - 完全免费
    - 不依赖第三方服务
    """

    def __init__(
        self,
        port: int,
        frp_path: str = r"E:\frp",
        server_addr: str = "localhost",
        server_port: int = 7000,
        subdomain: Optional[str] = None,
        agent_id: Optional[str] = None
    ):
        self.port = port
        self.frp_path = Path(frp_path)
        self.server_addr = server_addr
        self.server_port = server_port
        self.subdomain = subdomain or f"agent-{port}"
        self.agent_id = agent_id or f"agent-{port}"
        self._frpc_process: Optional[subprocess.Popen] = None
        self._public_url: Optional[str] = None
        self._remote_port: Optional[int] = None
        self._health_task: Optional[asyncio.Task] = None
        self._is_healthy = True

        # 重连保护
        self._reconnecting = False
        self._reconnect_count = 0
        self._max_reconnect_attempts = 3

        # FRP 可执行文件路径
        self._frpc_exe = self.frp_path / "frpc.exe"

    async def start(self) -> str:
        """启动 FRP 隧道 (TCP 模式)"""
        if not self._frpc_exe.exists():
            raise FileNotFoundError(
                f"FRP 客户端未找到: {self._frpc_exe}\n"
                f"请运行: e:\\hub\\frp\\install_frpc.bat"
            )

        # 使用确定性端口分配（基于 agent_id）
        self._remote_port = get_deterministic_port(self.agent_id)

        # 生成临时配置文件 (TCP 模式)
        config_content = f"""[common]
server_addr = {self.server_addr}
server_port = {self.server_port}
token = {self.token or os.getenv('FRP_TOKEN', '')}

[agent_tcp_{self._remote_port}]
type = tcp
local_ip = 127.0.0.1
local_port = {self.port}
remote_port = {self._remote_port}
"""

        config_file = self.frp_path / f"frpc_{self.port}.ini"
        config_file.write_text(config_content)

        # 启动 FRP 客户端
        self._frpc_process = subprocess.Popen(
            [str(self._frpc_exe), "-c", str(config_file)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        # 等待隧道建立（分层检测）
        await self._wait_for_tunnel()

        # 构建公网 URL (TCP 直连)
        self._public_url = f"http://{self.server_addr}:{self._remote_port}"

        # 启动健康检查任务
        self._health_task = asyncio.create_task(self._health_check_loop())

        return self._public_url

    async def _wait_for_tunnel(self, timeout: int = 15):
        """等待隧道建立 - 检测远程端口可达性"""
        start_time = time.time()

        # L1: 等待进程启动
        while time.time() - start_time < timeout:
            if self._frpc_process and self._frpc_process.poll() is None:
                break
            await asyncio.sleep(0.1)

        if not self._remote_port:
            raise RuntimeError("远程端口未分配")

        # L2: 检测远程端口可达性（真正的隧道检测）
        remote_url = f"http://{self.server_addr}:{self._remote_port}"
        check_start = time.time()
        while time.time() - check_start < timeout - 2:
            try:
                resp = await asyncio.to_thread(
                    lambda: httpx.get(f"{remote_url}/health", timeout=3)
                )
                if resp.status_code == 200:
                    print(f"[FRP] 隧道建立成功: {remote_url}")
                    return  # 远程端口可达，隧道真正建立
            except:
                pass
            await asyncio.sleep(1)

        # L3: 最后尝试检测 FRP Dashboard API
        try:
            response = await asyncio.to_thread(
                lambda: httpx.get(
                    f"http://{self.server_addr}:7500/api/proxy/tcp",
                    timeout=2,
                    auth=("admin", "hub_admin_2026")
                )
            )
            if response.status_code == 200:
                proxies = response.json()
                for proxy in proxies:
                    if str(self._remote_port) in str(proxy):
                        print(f"[FRP] Dashboard 确认隧道存在")
                        return
        except:
            pass

        raise TimeoutError(f"FRP 隧道建立超时 (远程端口 {self._remote_port})")

    async def _health_check_loop(self):
        """分层健康检查循环"""
        l1_counter = 0
        l2_counter = 0
        l3_counter = 0

        while True:
            try:
                # L1: 进程存活检查（每秒）
                l1_counter += 1
                if l1_counter >= 1:
                    l1_counter = 0
                    if not (self._frpc_process and self._frpc_process.poll() is None):
                        print("[FRP] L1: 进程已退出，尝试重连...")
                        await self._reconnect()

                # L2: FRP 控制通道检查（每10秒）
                l2_counter += 1
                if l2_counter >= 10:
                    l2_counter = 0
                    try:
                        resp = await asyncio.to_thread(
                            lambda: httpx.get(
                                f"http://{self.server_addr}:7500/api/serverinfo",
                                timeout=3,
                                auth=("admin", "hub_admin_2026")
                            )
                        )
                        if resp.status_code != 200:
                            print("[FRP] L2: 控制通道异常")
                    except:
                        print("[FRP] L2: 控制通道无响应")

                # L3: 公网可达性检查（每60秒，可选）
                l3_counter += 1
                if l3_counter >= 60:
                    l3_counter = 0
                    if self._public_url:
                        try:
                            resp = await asyncio.to_thread(
                                lambda: httpx.get(f"{self._public_url}/health", timeout=5)
                            )
                            self._is_healthy = resp.status_code == 200
                        except:
                            self._is_healthy = False
                            print("[FRP] L3: 公网不可达，尝试重连...")
                            await self._reconnect()

                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[FRP] 健康检查异常: {e}")
                await asyncio.sleep(5)

    async def _reconnect(self):
        """重连隧道 - 带锁和次数限制"""
        # 防止并发重连
        if self._reconnecting:
            print("[FRP] 已有重连任务进行中，跳过")
            return

        # 检查重连次数
        if self._reconnect_count >= self._max_reconnect_attempts:
            print(f"[FRP] 重连次数已达上限 ({self._max_reconnect_attempts})，停止尝试")
            self._is_healthy = False
            return

        self._reconnecting = True
        self._reconnect_count += 1

        try:
            print(f"[FRP] 正在重连... (第 {self._reconnect_count} 次)")
            self.stop()
            await asyncio.sleep(2)
            await self.start()
            # 重连成功，重置计数
            self._reconnect_count = 0
            self._is_healthy = True
            print("[FRP] 重连完成")
        except Exception as e:
            print(f"[FRP] 重连失败: {e}")
            self._is_healthy = False
        finally:
            self._reconnecting = False

    @property
    def is_healthy(self) -> bool:
        """返回隧道健康状态"""
        return self._is_healthy

    def stop(self):
        """停止隧道"""
        # 取消健康检查任务
        if self._health_task and not self._health_task.done():
            self._health_task.cancel()

        if self._frpc_process:
            self._frpc_process.terminate()
            try:
                self._frpc_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._frpc_process.kill()
            self._frpc_process = None

        # 清理配置文件
        config_file = self.frp_path / f"frpc_{self.port}.ini"
        if config_file.exists():
            config_file.unlink()

    @property
    def public_url(self) -> Optional[str]:
        """获取当前公网 URL"""
        return self._public_url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class TunnelManager:
    """
    隧道管理器兼容层

    自动选择：FRP > Ngrok
    """
    def __init__(
        self,
        port: int = 8000,
        backend: str = "auto"  # "auto", "frp", "ngrok"
    ):
        self.port = port
        self.backend = backend
        self._manager: Optional[FRPManager] = None

    async def start(self) -> str:
        """启动隧道"""
        if self.backend == "auto":
            # 优先使用 FRP
            try:
                self._manager = FRPManager(port=self.port)
                return await self._manager.start()
            except Exception as e:
                print(f"[FRP] 启动失败: {e}")
                print("[FRP] 回退到 Ngrok...")
                self.backend = "ngrok"

        if self.backend == "frp":
            self._manager = FRPManager(port=self.port)
            return await self._manager.start()

        elif self.backend == "ngrok":
            from .manager import TunnelManager as NgrokManager
            ngrok_mgr = NgrokManager(port=self.port)
            return await ngrok_mgr.start()

        raise ValueError(f"Unknown backend: {self.backend}")

    def stop(self):
        """停止隧道"""
        if self._manager:
            self._manager.stop()

    @property
    def public_url(self) -> Optional[str]:
        """获取当前公网 URL"""
        return self._manager.public_url if self._manager else None
