"""
API Key Configuration Script
============================
从 SECRETS.env 读取配置，写入 .env 文件
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def configure_from_secrets():
    """从项目根目录的 SECRETS.env 读取并写入 hub/.env"""
    secrets_path = PROJECT_ROOT.parent / "SECRETS.env"

    if not secrets_path.exists():
        print("=" * 50)
        print("请先在项目根目录创建 SECRETS.env")
        print(f"参考: {secrets_path}")
        print("或运行: python setup_secrets.py")
        print("=" * 50)
        return False

    # 解析 SECRETS.env
    secrets = {}
    for line in secrets_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            secrets[key.strip()] = value.strip()

    api_key = secrets.get("GLM_API_KEY", "")
    if not api_key:
        print("[ERROR] SECRETS.env 中 GLM_API_KEY 未配置")
        return False

    # 直接调用主配置脚本
    print(f"[OK] GLM_API_KEY 已从 SECRETS.env 加载")
    print(f"请运行: python {PROJECT_ROOT.parent / 'setup_secrets.py'}")
    return True


if __name__ == "__main__":
    configure_from_secrets()
