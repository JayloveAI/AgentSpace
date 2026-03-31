from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def init_workspace(base_dir: Optional[Path] = None, overwrite: bool = False) -> Path:
    """
    Initialize local workspace structure under ~/.agentspace.

    Creates:
    - demand_inbox/
    - supply_provided/
    - agentspace_config.yaml
    - inventory_map.json
    """
    workspace = Path(base_dir).expanduser() if base_dir else (Path.home() / ".agentspace")
    workspace.mkdir(parents=True, exist_ok=True)

    demand_inbox = workspace / "demand_inbox"
    supply_dir = workspace / "supply_provided"
    config_file = workspace / "agentspace_config.yaml"
    inventory_file = workspace / "inventory_map.json"

    demand_inbox.mkdir(parents=True, exist_ok=True)
    supply_dir.mkdir(parents=True, exist_ok=True)

    if overwrite or not inventory_file.exists():
        inventory_file.write_text(json.dumps({"files": []}, indent=2), encoding="utf-8")

    if overwrite or not config_file.exists():
        try:
            from ..discovery.config_scraper import generate_config
            generate_config(workspace_dir=workspace)
        except Exception:
            # Minimal fallback config (JSON is valid YAML)
            config = {
                "version": 1,
                "local_skills": [],
                "mcp_servers": []
            }
            config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")

    return workspace


if __name__ == "__main__":
    path = init_workspace()
    print(f"Workspace initialized at: {path}")
