from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from .skill_scanner import scan_skills


def _parse_mcp_servers(raw: str | None) -> list[dict]:
    if not raw:
        return []
    servers: list[dict] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        servers.append({"name": item, "endpoint": item})
    return servers


def generate_config(
    workspace_dir: Optional[Path | str] = None,
    skills_root: Optional[Path | str] = None
) -> dict:
    """
    Generate clawhub_config.yaml (JSON-compatible YAML).

    - local_skills: scanned from skills_root
    - mcp_servers: from MCP_SERVERS env (comma-separated)
    """
    workspace = Path(workspace_dir).expanduser() if workspace_dir else (Path.home() / ".clawhub")
    workspace.mkdir(parents=True, exist_ok=True)

    skills_root_path = Path(skills_root) if skills_root else (Path.cwd() / "skills")
    local_skills = scan_skills(skills_root_path) if skills_root_path.exists() else []

    mcp_servers = _parse_mcp_servers(os.getenv("MCP_SERVERS"))

    config = {
        "version": 1,
        "generated_at": datetime.utcnow().isoformat(),
        "local_skills": local_skills,
        "mcp_servers": mcp_servers,
    }

    config_path = workspace / "clawhub_config.yaml"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    return config
