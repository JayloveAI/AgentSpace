"""
Hub Server Configuration
========================
集中管理环境变量和配置项
"""
import os
from typing import Literal
from pathlib import Path

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    # 尝试加载项目根目录的 .env 文件
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv 未安装，使用系统环境变量


# ============================================================================
# 数据库配置
# ============================================================================
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://agenthub:agenthub_dev_password@localhost:5432/agent_hub"
)


# ============================================================================
# JWT 配置
# ============================================================================
# 对称加密密钥 - Hub 签发 JWT，客户端验证
# 开源时 SDK 内置默认值，企业部署通过环境变量覆盖
HUB_JWT_SECRET = os.getenv(
    "HUB_JWT_SECRET",
    "sk-hub-default-jwt-secret-2026"
)

# JWT 有效期（分钟）- 10分钟内必须完成握手
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "10"))


# ============================================================================
# Embedding API 配置 (支持 OpenAI / GLM-5)
# ============================================================================
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai")  # openai 或 glm

# OpenAI 配置
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")

# GLM-5 (智谱) 配置
# 优先使用环境变量，如果没有则使用硬编码的 API Key
GLM_API_KEY = os.getenv("GLM_API_KEY", "")
if not GLM_API_KEY:
    # 硬编码 API Key（仅用于测试）
    GLM_API_KEY = "e6edc7b93f2d4b1e8280b73d37228e40.pOs5JhSDSFOxqcfG"
GLM_EMBEDDING_MODEL = os.getenv("GLM_EMBEDDING_MODEL", "embedding-3")

# 根据提供商选择配置
if EMBEDDING_PROVIDER == "glm":
    EMBEDDING_API_KEY = GLM_API_KEY
    EMBEDDING_MODEL = GLM_EMBEDDING_MODEL
    # GLM embedding-2: 1024维, embedding-3: 2048维
    EMBEDDING_DIMENSIONS = 2048 if GLM_EMBEDDING_MODEL == "embedding-3" else 1024
else:
    EMBEDDING_API_KEY = OPENAI_API_KEY
    EMBEDDING_MODEL = OPENAI_EMBEDDING_MODEL
    EMBEDDING_DIMENSIONS = 1536  # OpenAI ada-002 是 1536 维


# ============================================================================
# Hub 服务配置
# ============================================================================
HUB_BASE_URL = os.getenv("HUB_BASE_URL", "http://localhost:8000")
API_V1_PREFIX = "/api/v1"

# 环境标识
ENV = os.getenv("ENV", "development")
DEBUG = ENV == "development"


# ============================================================================
# 搜索配置
# ============================================================================
# 默认返回 Top N 匹配结果
DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K", "3"))

# 相似度阈值（0-1，低于此值不返回）
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))


# ============================================================================
# 安全配置
# ============================================================================
# CORS 允许的源
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "*"
).split(",") if os.getenv("CORS_ORIGINS") != "*" else ["*"]


# ============================================================================
# 验证配置
# ============================================================================
def validate_config() -> Literal[True]:
    """验证关键配置项是否完整"""
    import sys

    errors = []

    if EMBEDDING_PROVIDER == "glm":
        if not GLM_API_KEY:
            errors.append("GLM_API_KEY 未设置 - Embedding 功能将不可用")
    else:
        if not OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY 未设置 - Embedding 功能将不可用")

    if errors:
        print("[WARNING] Configuration warnings:")
        for error in errors:
            print(f"   - {error}")
    else:
        print(f"[OK] Embedding provider: {EMBEDDING_PROVIDER.upper()} ({EMBEDDING_MODEL})")

    return True


# 启动时验证
validate_config()
