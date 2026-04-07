from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


class FileExtensionWhitelist:
    """Simple file extension allowlist."""

    DEFAULT_ALLOWED = {".csv", ".json", ".xlsx", ".pdf", ".txt", ".md", ".docx", ".pptx",
                     ".db", ".sqlite", ".sqlite3", ".mdb", ".accdb", ".xml",
                     # V1.6.7: 多模态文件类型支持
                     ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg",
                     ".mp3", ".wav", ".mp4", ".avi", ".mkv", ".mov",
                     ".zip", ".tar", ".gz", ".rar", ".7z",
                     ".py", ".js", ".ts", ".html", ".css", ".yaml", ".yml", ".toml"}

    def __init__(self, allowed: Iterable[str] | None = None):
        if allowed is not None:
            self.allowed = {ext.lower() for ext in allowed}
            return

        env = os.getenv("AGENTSPACE_ALLOWED_EXTS")
        if env:
            self.allowed = {ext.strip().lower() for ext in env.split(",") if ext.strip()}
        else:
            self.allowed = set(self.DEFAULT_ALLOWED)

    def validate_file(self, filename: str) -> tuple[bool, str | None]:
        ext = Path(filename).suffix.lower()
        if ext in self.allowed:
            return True, None
        return False, f"File extension '{ext}' is not allowed"
