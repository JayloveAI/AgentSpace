# -*- coding: utf-8 -*-
"""
Transfer Strategy — 文件传输策略选择器

三策略自动分流：
  < 10MB   → Strategy A: base64 JSON（现有，不变）
  10-100MB → Strategy B: 分块流式传输
  > 100MB  → Strategy C: R2 中转 + AES 加密

V2.0 设计（基于架构评审修正）：
- 原子化写入（.downloading 后缀）
- 流式 AES-256 加解密（不占内存）
- 文本文件 gzip 压缩
"""
from __future__ import annotations

import os
import hashlib
import secrets
import base64
from pathlib import Path
from typing import AsyncGenerator, Literal

# ==================== 阈值常量 ====================
SMALL_FILE_THRESHOLD = 10 * 1024 * 1024    # 10MB
LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100MB
CHUNK_SIZE = 4 * 1024 * 1024              # 4MB

# 可压缩扩展名（文本类）
COMPRESSIBLE_EXTS = {
    ".txt", ".md", ".json", ".csv", ".xml", ".html", ".yaml", ".yml",
    ".toml", ".py", ".js", ".ts", ".css", ".log", ".sql", ".sh",
}

StrategyType = Literal["base64", "stream", "external"]


def select_strategy(file_path: str | Path) -> StrategyType:
    """根据文件大小自动选择传输策略"""
    file_size = os.path.getsize(file_path)
    if file_size < SMALL_FILE_THRESHOLD:
        return "base64"
    elif file_size < LARGE_FILE_THRESHOLD:
        return "stream"
    else:
        return "external"


def is_compressible(file_path: str | Path) -> bool:
    """判断文件是否适合压缩（文本类文件）"""
    ext = Path(file_path).suffix.lower()
    return ext in COMPRESSIBLE_EXTS


def estimate_timeout(file_size: int, strategy: StrategyType) -> float:
    """自适应超时估算（秒）"""
    if strategy == "base64":
        return 60.0
    elif strategy == "stream":
        # 按 2MB/s 估算，最少 60s，最多 600s
        return min(600.0, max(60.0, file_size / (2 * 1024 * 1024)))
    else:  # external
        return 300.0


def generate_aes_key() -> str:
    """生成随机 AES-256 密钥，返回 base64 编码"""
    key = secrets.token_bytes(32)  # 256 bits
    return base64.b64encode(key).decode("utf-8")


def aes_key_to_bytes(b64_key: str) -> bytes:
    """base64 编码的密钥转为原始字节"""
    return base64.b64decode(b64_key)


def compute_sha256(file_path: str | Path) -> str:
    """计算文件 SHA-256（流式，不占内存）"""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()


async def aes_encrypt_chunks(
    file_path: str | Path,
    key: bytes,
) -> AsyncGenerator[bytes, None]:
    """
    流式 AES 加密文件（CTR 模式，无需填充）

    每个分块独立加密，接收方可以流式解密。
    格式: nonce(12 bytes) + counter(4 bytes) + ciphertext

    Args:
        file_path: 文件路径
        key: AES-256 密钥 (32 bytes)
    """
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    nonce = secrets.token_bytes(12)  # 96-bit nonce
    # 发送 nonce 作为第一个分块
    yield nonce

    counter = 0
    cipher = Cipher(algorithms.AES(key), modes.CTR(nonce + counter.to_bytes(4, "big")))
    encryptor = cipher.encryptor()

    try:
        import aiofiles
        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(CHUNK_SIZE):
                encrypted = encryptor.update(chunk)
                yield encrypted
        # 最终块
        final = encryptor.finalize()
        if final:
            yield final
    except ImportError:
        # aiofiles 未安装，退回同步读取
        with open(file_path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                encrypted = encryptor.update(chunk)
                yield encrypted
        final = encryptor.finalize()
        if final:
            yield final


async def aes_decrypt_chunks(
    encrypted_source: AsyncGenerator[bytes, None] | bytes,
    key: bytes,
    nonce: bytes,
) -> AsyncGenerator[bytes, None]:
    """
    流式 AES 解密（CTR 模式）

    Args:
        encrypted_source: 加密数据源（异步生成器或字节）
        key: AES-256 密钥 (32 bytes)
        nonce: 12-byte nonce
    """
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    counter = 0
    cipher = Cipher(algorithms.AES(key), modes.CTR(nonce + counter.to_bytes(4, "big")))
    decryptor = cipher.decryptor()

    if isinstance(encrypted_source, bytes):
        yield decryptor.update(encrypted_source) + decryptor.finalize()
        return

    async for chunk in encrypted_source:
        decrypted = decryptor.update(chunk)
        yield decrypted

    final = decryptor.finalize()
    if final:
        yield final


class TransferProgress:
    """传输进度追踪器"""

    def __init__(self, total_bytes: int, label: str = "Transfer"):
        self.total_bytes = total_bytes
        self.transferred_bytes = 0
        self.label = label
        self._last_pct = -1

    def update(self, chunk_bytes: int) -> None:
        """更新进度，每 10% 打印一次"""
        self.transferred_bytes += chunk_bytes
        pct = int(self.transferred_bytes / self.total_bytes * 10) * 10
        if pct > self._last_pct and pct <= 100:
            self._last_pct = pct
            mb_done = self.transferred_bytes / (1024 * 1024)
            mb_total = self.total_bytes / (1024 * 1024)
            print(f"[{self.label}] {pct}% ({mb_done:.1f}/{mb_total:.1f} MB)")

    @property
    def is_complete(self) -> bool:
        return self.transferred_bytes >= self.total_bytes


def atomic_write_path(dest: Path) -> Path:
    """获取原子写入的临时文件路径"""
    return dest.with_suffix(dest.suffix + ".downloading")
