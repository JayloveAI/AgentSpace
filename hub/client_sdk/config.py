"""Client SDK Configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from AgentSpace workspace first
agentspace_env = Path.home() / ".agentspace" / ".env"
if agentspace_env.exists():
    try:
        # Try UTF-8 first
        load_dotenv(agentspace_env, encoding="utf-8")
    except (UnicodeDecodeError, Exception):
        try:
            # Fallback to system default encoding
            load_dotenv(agentspace_env)
        except Exception:
            # If still fails, try reading with different encodings
            import codecs
            for encoding in ["utf-8-sig", "gbk", "latin-1"]:
                try:
                    content = agentspace_env.read_text(encoding=encoding)
                    # Manually parse and set environment variables
                    for line in content.splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            os.environ[key.strip()] = value.strip()
                    break
                except Exception:
                    continue
else:
    # Fallback to current directory for development
    try:
        load_dotenv(encoding="utf-8")
    except Exception:
        load_dotenv()

# JWT secret for local signing / verification
HUB_JWT_SECRET = os.getenv("HUB_JWT_SECRET", "")

# Hub endpoint
HUB_URL = os.getenv("HUB_URL", "http://localhost:8000")
API_V1_PREFIX = "/api/v1"

# Local agent network
LOCAL_PORT = int(os.getenv("LOCAL_PORT", "8000"))
LOCAL_HOST = os.getenv("LOCAL_HOST", "127.0.0.1")

# Ngrok config
NGROK_AUTHTOKEN = os.getenv("NGROK_AUTHTOKEN", "")
NGROK_REGION = os.getenv("NGROK_REGION", "us")

# Identity path
DEFAULT_IDENTITY_PATH = os.getenv("IDENTITY_PATH", "identity.md")

# Region / tunnel selection
AGENTSPACE_REGION = os.getenv("AGENTSPACE_REGION", "global").lower()
TUNNEL_PROVIDER = os.getenv("TUNNEL_PROVIDER")

# FRP Tunnel Configuration
FRP_TOKEN = os.getenv("FRP_TOKEN", "")
FRP_SERVER_ADDR = os.getenv("FRP_SERVER_ADDR", "")
FRP_SERVER_PORT = int(os.getenv("FRP_SERVER_PORT", "7000"))
FRP_EXECUTABLE = os.getenv("FRP_EXECUTABLE", "frpc")


def get_region() -> str:
    region = os.getenv("AGENTSPACE_REGION", AGENTSPACE_REGION).lower()
    return region if region in {"cn", "global"} else "global"


def get_tunnel_provider() -> str | None:
    provider = os.getenv("TUNNEL_PROVIDER", TUNNEL_PROVIDER or "").strip().lower()
    return provider or None
