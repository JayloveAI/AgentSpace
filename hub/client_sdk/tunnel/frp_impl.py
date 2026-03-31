from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from pathlib import Path

from .base import BaseTunnel


def get_deterministic_port(agent_id: str, base: int = 8001, range_size: int = 999) -> int:
    """基于 agent_id 计算确定性端口（零网络依赖）"""
    hash_bytes = hashlib.sha256(agent_id.encode()).digest()
    port_offset = int.from_bytes(hash_bytes[:4], 'big') & 0x7FFFFFFF
    return base + (port_offset % range_size)


class FrpTunnel(BaseTunnel):
    """FRP-based tunnel (TCP mode for MVP)."""

    def __init__(self, server_addr: str, server_port: int, token: str | None, frp_executable: str | None = None, agent_id: str | None = None):
        self.server_addr = server_addr
        self.server_port = server_port
        self.token = token or ""
        self.agent_id = agent_id or "default-agent"
        self._process: subprocess.Popen | None = None
        self._assigned_port: int | None = None
        self._config_file: str | None = None

        # 从环境变量或参数获取 FRP 可执行文件路径
        self._frp_executable = frp_executable or os.getenv("FRP_EXECUTABLE", "frpc")

    async def start(self, port: int) -> str:
        # 使用确定性端口分配（基于 agent_id）
        remote_port = get_deterministic_port(self.agent_id)
        self._assigned_port = remote_port

        # TOML format for FRP 0.53+
        config_content = f'''serverAddr = "{self.server_addr}"
serverPort = {self.server_port}
auth.token = "{self.token or ''}"

[[proxies]]
name = "{self.agent_id}"
type = "tcp"
localIP = "127.0.0.1"
localPort = {port}
remotePort = {remote_port}
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False, encoding="utf-8", newline="\n") as f:
            f.write(config_content)
            self._config_file = f.name

        self._process = subprocess.Popen(
            [self._frp_executable, "-c", self._config_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )

        # 返回 TCP 访问地址
        return f"http://{self.server_addr}:{remote_port}"

    def stop(self) -> None:
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            self._process = None

        # 清理临时配置文件
        if self._config_file and os.path.exists(self._config_file):
            try:
                os.unlink(self._config_file)
            except OSError:
                pass
            self._config_file = None

    @property
    def is_active(self) -> bool:
        return self._process is not None and self._process.poll() is None
