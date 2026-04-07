# -*- coding: utf-8 -*-
"""
R2 Storage — Cloudflare R2 对象存储适配器

S3 兼容 API，使用 boto3 连接 Cloudflare R2。
下行流量免费，适合作为大文件中转站。
"""
from __future__ import annotations

import os
import hashlib
from pathlib import Path
from typing import Optional

from client_sdk.core.transfer_strategy import CHUNK_SIZE, TransferProgress


class R2Storage:
    """Cloudflare R2 存储适配器（S3 兼容）"""

    def __init__(
        self,
        account_id: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        public_url: str = "",
    ):
        self.account_id = account_id
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket
        self.public_url = public_url
        self._client = None

    @property
    def endpoint_url(self) -> str:
        return f"https://{self.account_id}.r2.cloudflarestorage.com"

    @property
    def client(self):
        """懒加载 boto3 S3 client"""
        if self._client is None:
            import boto3
            from botocore.config import Config

            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                config=Config(
                    region_name="auto",
                    retries={"max_attempts": 3, "mode": "adaptive"},
                ),
            )
        return self._client

    def is_configured(self) -> bool:
        """检查 R2 是否已配置"""
        return bool(self.account_id and self.access_key and self.secret_key)

    def upload_file(
        self,
        file_path: str | Path,
        key: Optional[str] = None,
        progress_callback=None,
    ) -> tuple[str, str]:
        """
        上传文件到 R2（流式分片上传，支持大文件）

        Args:
            file_path: 本地文件路径
            key: R2 对象键（默认用文件名）
            progress_callback: 进度回调

        Returns:
            (presigned_url, sha256)
        """
        file_path = Path(file_path)
        if key is None:
            key = file_path.name

        # 计算 SHA-256
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                sha256.update(chunk)
        checksum = sha256.hexdigest()

        # 分片上传
        file_size = file_path.stat().st_size
        progress = TransferProgress(file_size, "R2 Upload")

        # 使用 boto3 分片上传
        from boto3.s3.transfer import TransferConfig

        transfer_config = TransferConfig(
            multipart_threshold=8 * 1024 * 1024,   # > 8MB 分片
            multipart_chunksize=CHUNK_SIZE,
            max_concurrency=4,
        )

        def _progress_cb(bytes_transferred):
            progress.update(bytes_transferred - progress.transferred_bytes)

        self.client.upload_file(
            str(file_path),
            self.bucket,
            key,
            Config=transfer_config,
            Callback=_progress_cb if file_size > SMALL_FILE_THRESHOLD else None,
        )

        # 生成预签名 URL（1 小时有效）
        url = self.generate_presigned_url(key, expires=3600)
        return url, checksum

    def download_file(
        self,
        url: str,
        dest_path: str | Path,
        expected_size: int = 0,
    ) -> bool:
        """
        从 URL 下载文件到本地（流式，4MB 分块）

        支持预签名 URL 或直接 R2 key。

        Args:
            url: 下载 URL（预签名或公共）
            dest_path: 本地目标路径
            expected_size: 预期文件大小（用于进度）

        Returns:
            是否成功
        """
        import httpx

        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # 原子写入：先写 .downloading 临时文件
        tmp_path = dest_path.with_suffix(dest_path.suffix + ".downloading")

        try:
            progress = TransferProgress(expected_size or 1, "R2 Download")

            with httpx.stream("GET", url, timeout=600.0, follow_redirects=True) as response:
                response.raise_for_status()
                with open(tmp_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=CHUNK_SIZE):
                        f.write(chunk)
                        progress.update(len(chunk))

            # 原子 rename
            tmp_path.rename(dest_path)
            return True

        except Exception as e:
            print(f"[R2] Download failed: {e}")
            # 清理脏数据
            if tmp_path.exists():
                tmp_path.unlink()
            return False

    def generate_presigned_url(self, key: str, expires: int = 3600) -> str:
        """生成预签名下载 URL"""
        url = self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires,
        )

        # 如果配置了自定义域名，替换 endpoint
        if self.public_url:
            url = url.replace(self.endpoint_url, self.public_url)

        return url

    def delete_object(self, key: str) -> None:
        """删除 R2 对象"""
        self.client.delete_object(Bucket=self.bucket, Key=key)


# 模块级便捷函数
_storage_instance: Optional[R2Storage] = None


def get_r2_storage() -> R2Storage:
    """获取全局 R2 存储实例（从 config 模块读取配置）"""
    global _storage_instance
    if _storage_instance is None:
        from client_sdk.config import (
            R2_ACCOUNT_ID, R2_ACCESS_KEY, R2_SECRET_KEY, R2_BUCKET, R2_PUBLIC_URL,
        )
        _storage_instance = R2Storage(
            account_id=R2_ACCOUNT_ID,
            access_key=R2_ACCESS_KEY,
            secret_key=R2_SECRET_KEY,
            bucket=R2_BUCKET,
            public_url=R2_PUBLIC_URL,
        )
    return _storage_instance


# 常量引用
SMALL_FILE_THRESHOLD = 10 * 1024 * 1024
