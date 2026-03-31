"""
Match Service - 向量语义撮合服务
================================
负责向量化处理和语义相似度检索

支持: OpenAI / GLM-5 (智谱)

V1.6.4 优化版本:
- P1-1: httpx.AsyncClient 连接池，复用 TCP 连接
- P1-2: Exponential backoff 重试机制，提高容错性
- P1-3: 批量 Embedding 支持，减少 API 调用
- VectorCache: Embedding 预计算 + 缓存，避免重复计算
"""
import asyncio
import hashlib
import httpx
from typing import Optional, Literal, List, Dict
from datetime import datetime
from hub_server.config import (
    EMBEDDING_API_KEY, EMBEDDING_MODEL,
    EMBEDDING_PROVIDER, EMBEDDING_DIMENSIONS,
    SIMILARITY_THRESHOLD
)


class VectorCache:
    """
    Embedding 向量缓存
    - 基于文本 hash 缓存向量
    - 支持 LRU 淘汰（可选）
    - 避免重复计算相同文本的向量
    """

    def __init__(self, max_size: int = 10000):
        self._cache: Dict[str, List[float]] = {}
        self._max_size = max_size

    def _hash_text(self, text: str) -> str:
        """生成文本的 SHA256 哈希"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def get(self, text: str) -> Optional[List[float]]:
        """从缓存获取向量"""
        key = self._hash_text(text)
        return self._cache.get(key)

    def set(self, text: str, vector: List[float]) -> None:
        """存入缓存"""
        if len(self._cache) >= self._max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        key = self._hash_text(text)
        self._cache[key] = vector

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()

    def size(self) -> int:
        """缓存大小"""
        return len(self._cache)


vector_cache = VectorCache()


class EmbeddingService:
    """Embedding 服务 - 支持 OpenAI 和 GLM-5"""

    PROVIDERS = {
        "openai": {
            "url": "https://api.openai.com/v1/embeddings",
            "model": "text-embedding-ada-002",
            "dimensions": 1536
        },
        "glm": {
            "url": "https://open.bigmodel.cn/api/paas/v4/embeddings",
            "model": "embedding-2",
            "dimensions": 1024
        }
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[Literal["openai", "glm"]] = None
    ):
        self.api_key = api_key or EMBEDDING_API_KEY
        self.model = model or EMBEDDING_MODEL
        self.provider = provider or EMBEDDING_PROVIDER
        self.config = self.PROVIDERS[self.provider]
        self._client: Optional[httpx.AsyncClient] = None
        self._retry_delays = [1, 2, 4, 8, 16]

    async def _get_client(self) -> httpx.AsyncClient:
        """
        P1-1: 获取或创建 AsyncClient（连接池复用）

        使用单例模式复用 httpx.AsyncClient：
        - 复用 TCP 连接，减少连接建立开销
        - 自动管理连接池
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(
                    max_keepalive_connections=20,
                    max_connections=100,
                    keepalive_expiry=120.0
                )
            )
        return self._client

    async def close(self) -> None:
        """关闭 AsyncClient"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def get_embedding(self, text: str) -> List[float]:
        """
        获取文本的向量表示（带缓存和重试）

        关键决策：在 Hub 服务端进行向量化
        - 客户端无需配置 API Key
        - 降低接入门槛，符合"极简"原则
        """
        cached = vector_cache.get(text)
        if cached is not None:
            return cached

        if not self.api_key:
            raise ValueError("EMBEDDING_API_KEY 未配置")

        last_exception = None
        for delay in self._retry_delays:
            try:
                client = await self._get_client()
                response = await client.post(
                    self.config["url"],
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "input": text
                    }
                )
                response.raise_for_status()

                data = response.json()
                vector = data["data"][0]["embedding"]

                vector_cache.set(text, vector)
                return vector

            except httpx.HTTPError as e:
                last_exception = e
                if delay < self._retry_delays[-1]:
                    await asyncio.sleep(delay)
                    continue
                break
            except Exception as e:
                last_exception = e
                break

        raise RuntimeError(
            f"Embedding API 调用失败 ({self.provider})，已重试 {len(self._retry_delays)} 次: {str(last_exception)}"
        )

    async def batch_get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        P1-3: 批量获取向量（优化 API 调用次数）

        策略：
        1. 先从缓存获取已有的向量
        2. 剩余文本批量调用 API
        3. 结果存入缓存
        """
        if not texts:
            return []

        results: List[Optional[List[float]]] = [None] * len(texts)
        batch_texts: List[tuple[int, str]] = []

        for i, text in enumerate(texts):
            cached = vector_cache.get(text)
            if cached is not None:
                results[i] = cached
            else:
                batch_texts.append((i, text))

        if not batch_texts:
            return results

        if not self.api_key:
            raise ValueError("EMBEDDING_API_KEY 未配置")

        indices = [item[0] for item in batch_texts]
        inputs = [item[1] for item in batch_texts]

        last_exception = None
        for delay in self._retry_delays:
            try:
                client = await self._get_client()
                response = await client.post(
                    self.config["url"],
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "input": inputs
                    }
                )
                response.raise_for_status()

                data = response.json()
                embeddings = [item["embedding"] for item in data["data"]]

                for idx, embedding in zip(indices, embeddings):
                    results[idx] = embedding
                    vector_cache.set(inputs[idx], embedding)

                return results

            except httpx.HTTPError as e:
                last_exception = e
                if delay < self._retry_delays[-1]:
                    await asyncio.sleep(delay)
                    continue
                break
            except Exception as e:
                last_exception = e
                break

        raise RuntimeError(
            f"批量 Embedding API 调用失败 ({self.provider})，已重试 {len(self._retry_delays)} 次: {str(last_exception)}"
        )


class MatchService:
    """撮合服务 - 向量检索 + 业务过滤"""

    def __init__(self, db_conn, embedding_service: EmbeddingService):
        self.db = db_conn
        self.embedding = embedding_service

    async def publish_agent(
        self,
        agent_id: str,
        domain: str,
        intent_type: str,
        contact_endpoint: str,
        description: str
    ) -> dict:
        """
        发布/更新 Agent 名片

        1. 对 description 进行向量化
        2. 存入数据库
        3. 返回注册结果
        """
        description_vector = await self.embedding.get_embedding(description)

        return {
            "agent_id": agent_id,
            "status": "registered",
            "vector_dim": len(description_vector)
        }

    async def search_agents(
        self,
        query: str,
        domain: Optional[str] = None,
        top_k: int = 3
    ) -> List[dict]:
        """
        V1.5 Hybrid Search: SQL hard filter + vector soft rank

        Strategy:
        1. SQL WHERE: domain = ? AND node_status = 'active' (hard filter)
        2. Vector similarity: cosine distance (soft ranking)
        3. Performance: Disable sequential scan to ensure HNSW index is used

        Returns agents with:
        - agent_id, contact_endpoint, tasks_provided
        - node_status, live_broadcast
        - similarity_score (0-1)
        """
        query_vector = await self.embedding.get_embedding(query)

        candidates = self._search_agents_in_store(query_vector, domain, top_k)

        if not candidates:
            return []

        scored = []
        for agent in candidates:
            similarity = self._cosine_similarity(query_vector, agent["description_vector"])
            if similarity > SIMILARITY_THRESHOLD:
                scored.append({
                    "agent_id": agent["agent_id"],
                    "contact_endpoint": agent["contact_endpoint"],
                    "match_token": self._issue_mock_token(agent["agent_id"]),
                    "tasks_provided": agent.get("tasks_provided", 0),
                    "node_status": agent.get("node_status", "active"),
                    "live_broadcast": agent.get("live_broadcast", ""),
                    "similarity_score": round(similarity, 4)
                })

        scored.sort(key=lambda x: x["similarity_score"], reverse=True)
        return scored[:top_k]

    def _search_agents_in_store(
        self,
        query_vector: List[float],
        domain: Optional[str],
        top_k: int
    ) -> List[dict]:
        """
        在内存存储中搜索 Agent（开发阶段用）

        TODO: 替换为 PostgreSQL + pgvector 真实查询
        """
        from hub_server.api.routes import _agent_store

        candidates = [
            agent for agent in _agent_store.values()
            if agent.get("intent_type") == "bid"
            and agent.get("node_status", "offline") == "active"
        ]

        if domain:
            candidates = [a for a in candidates if a.get("domain") == domain]

        return candidates

    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """计算余弦相似度"""
        import numpy as np
        a, b = np.array(vec_a), np.array(vec_b)
        norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _issue_mock_token(self, agent_id: str) -> str:
        """签发 mock token（开发阶段用）"""
        return f"mock.token.{agent_id}"

    async def update_status(
        self,
        agent_id: str,
        node_status: Literal["active", "busy", "offline"],
        live_broadcast: Optional[str] = None
    ) -> dict:
        """
        V1.5 Update agent live status and regenerate search vector

        Key Design:
        - node_status: For SQL WHERE filtering (hard filter)
        - live_broadcast: Combined with identity for vector embedding (soft ranking)

        Vector = identity_text + live_broadcast
        This makes search results reflect current agent availability
        """
        combined_text = f"Agent {agent_id}\n{live_broadcast or 'No message'}"
        new_vector = await self.embedding.get_embedding(combined_text)

        return {
            "agent_id": agent_id,
            "node_status": node_status,
            "live_broadcast": live_broadcast,
            "status_updated_at": datetime.utcnow().isoformat(),
            "vector_regenerated": True
        }


embedding_service = EmbeddingService(
    api_key=EMBEDDING_API_KEY,
    model=EMBEDDING_MODEL,
    provider=EMBEDDING_PROVIDER
)
