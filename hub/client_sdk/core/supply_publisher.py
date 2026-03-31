"""Supply Publisher - Announce new files to Hub for demand matching."""
import httpx
from typing import List, Dict
from ..config import HUB_URL, API_V1_PREFIX


class SupplyPublisher:
    """Publish file supply information to Hub for automatic demand matching."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.hub_url = f"{HUB_URL}{API_V1_PREFIX}"
        print(f"[DEBUG-SDK] ========== SupplyPublisher Init ==========")
        print(f"[DEBUG-SDK] HUB_URL: {HUB_URL}")
        print(f"[DEBUG-SDK] API_V1_PREFIX: {API_V1_PREFIX}")
        print(f"[DEBUG-SDK] Final hub_url: {self.hub_url}")
        print(f"[DEBUG-SDK] agent_id: {self.agent_id}")
        print(f"[DEBUG-SDK] =========================================")

    async def publish_supply(self, file_info: Dict, tags: List[str]) -> List[Dict]:
        """
        Publish supply to Hub and get matching demands.

        Args:
            file_info: File metadata (filename, size, local_path)
            tags: Extracted entity tags from filename

        Returns:
            List of matched demands, each containing:
            - demand_id: Demand identifier
            - resource_type: Expected resource type
            - description: Demand description
            - seeker_webhook_url: Seeker's delivery address
        """
        resource_type = file_info["filename"].split(".")[-1]

        # 🔍 Debug logging
        print(f"[DEBUG-SDK] ========== Publishing Supply ==========")
        print(f"[DEBUG-SDK] agent_id: {self.agent_id}")
        print(f"[DEBUG-SDK] resource_type: {resource_type}")
        print(f"[DEBUG-SDK] tags: {tags}")
        print(f"[DEBUG-SDK] URL: {self.hub_url}/agents/{self.agent_id}/supply")

        # ⚠️ 关键修正：传 None，让 Hub 计算真实语义向量
        payload = {
            "agent_id": self.agent_id,
            "resource_type": resource_type,
            "tags": tags,
            "supply_vector": None,
            "live_broadcast": f"新增资源: {file_info['filename']}",
            "webhook_url": None
        }

        print(f"[DEBUG-SDK] Request Payload: {payload}")
        print(f"[DEBUG-SDK] Request URL: {self.hub_url}/agents/{self.agent_id}/supply")
        print(f"[DEBUG-SDK] Sending request to Hub...")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.hub_url}/agents/{self.agent_id}/supply",
                    json=payload
                )

                print(f"[DEBUG-SDK] Response Status: {response.status_code}")
                print(f"[DEBUG-SDK] Response Body: {response.text}")

                if response.status_code == 200:
                    data = response.json()
                    matched = data.get("matched_demands", [])
                    print(f"[DEBUG-SDK] ✓ Response HTTP 200")
                    print(f"[DEBUG-SDK] Matched demands count: {len(matched)}")
                    for m in matched:
                        print(f"[DEBUG-SDK]   - demand_id={m.get('demand_id')}, resource_type={m.get('resource_type')}")
                    print(f"[DEBUG-SDK] ========================================")
                    return matched
                else:
                    print(f"[DEBUG-SDK] ✗ Supply publish failed: HTTP {response.status_code}")
                    print(f"[DEBUG-SDK] Response: {response.text}")
                    return []

        except Exception as e:
            print(f"[DEBUG-SDK] ✗ Exception occurred: {e}")
            import traceback
            traceback.print_exc()
            return []
