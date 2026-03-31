from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict

import jwt

from ..config import HUB_JWT_SECRET


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ProvenanceSigner:
    """Sign and verify file provenance metadata using JWT (HS256)."""

    def __init__(self, secret: str | None = None):
        self.secret = secret or HUB_JWT_SECRET

    def sign(self, payload: Dict[str, Any]) -> str:
        return jwt.encode(payload, self.secret, algorithm="HS256")

    def verify(self, token: str) -> Dict[str, Any]:
        return jwt.decode(token, self.secret, algorithms=["HS256"])


def build_provenance(filename: str, content: bytes, provider_id: str | None = None) -> Dict[str, Any]:
    return {
        "filename": filename,
        "hash": hash_bytes(content),
        "provider_id": provider_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
