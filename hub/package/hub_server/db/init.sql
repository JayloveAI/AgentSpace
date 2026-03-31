-- Agent Universal Hub Database Initialization
-- 启用 pgvector 扩展并创建核心表
--
-- 向量维度说明:
-- - OpenAI (text-embedding-ada-002): 1536 维
-- - GLM-5 (embedding-2): 1024 维
--
-- 使用最大维度 1536 以兼容所有提供商
-- (pgvector 支持存储比配置更大的向量，只在使用时校验)

-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- Agent 档案表
CREATE TABLE IF NOT EXISTS agent_profiles (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(255) UNIQUE NOT NULL,
    domain VARCHAR(50) NOT NULL,
    intent_type VARCHAR(20) NOT NULL CHECK (intent_type IN ('ask', 'bid')),
    contact_endpoint VARCHAR(512) NOT NULL,
    description TEXT NOT NULL,
    description_vector VECTOR(1536),  -- 最大维度，兼容所有提供商
    tasks_requested INT DEFAULT 0,
    tasks_provided INT DEFAULT 0,
    last_active TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 索引优化
CREATE INDEX idx_agent_profiles_agent_id ON agent_profiles(agent_id);
CREATE INDEX idx_agent_profiles_domain ON agent_profiles(domain);
CREATE INDEX idx_agent_profiles_intent_type ON agent_profiles(intent_type);

-- HNSW 向量索引 - 高性能近似最近邻搜索
CREATE INDEX idx_agent_profiles_vector ON agent_profiles
    USING hnsw (description_vector vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- 任务完成记录表（用于防重）
CREATE TABLE IF NOT EXISTS task_completions (
    id SERIAL PRIMARY KEY,
    match_token_hash VARCHAR(64) UNIQUE NOT NULL,  -- JWT 的 SHA256 哈希
    requester_id VARCHAR(255) NOT NULL,
    provider_id VARCHAR(255) NOT NULL,
    completed_at TIMESTAMP DEFAULT NOW()
);

-- 插入测试数据（可选）
INSERT INTO agent_profiles (agent_id, domain, intent_type, contact_endpoint, description, description_vector, tasks_provided)
VALUES 
    ('english_corpus_bot', 'education', 'bid', 'https://example.ngrok.app/api/webhook', 
     '专门处理 K-12 英文阅读资料，将原始文本转换为 Obsidian 双链 Markdown 格式', 
     '[0.1, 0.2, ...]'::vector(1536), 342)
ON CONFLICT (agent_id) DO NOTHING;
