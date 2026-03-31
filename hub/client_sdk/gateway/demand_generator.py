from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from client_sdk.core.entity_extractor import EntityExtractor


@dataclass
class DemandTicket:
    demand_id: str
    resource_type: str
    description: str
    tags: list[str]
    created_at: str
    seeker_id: str | None = None


class DemandGenerator:
    """Generate a demand ticket from resource-missing context."""

    def __init__(self):
        self._extractor = EntityExtractor()

    async def generate_ticket(self, context: dict) -> DemandTicket:
        resource_type = context.get("resource_type", "resource")
        description = context.get("description", "")
        seeker_id = context.get("seeker_id")

        tags = self._extractor.extract_tags(description)
        if not tags:
            tags = [resource_type]

        return DemandTicket(
            demand_id=str(uuid.uuid4()),
            resource_type=resource_type,
            description=description,
            tags=tags,
            created_at=datetime.utcnow().isoformat(),
            seeker_id=seeker_id,
        )
