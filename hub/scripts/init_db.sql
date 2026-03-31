-- Agent Universal Hub 数据库初始化脚本
-- 在 PostgreSQL 容器首次启动时自动执行

-- 创建 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 创建 agent_profiles 表
CREATE TABLE IF NOT EXISTS agent_profiles (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(255) UNIQUE NOT NULL,
    domain VARCHAR(50) NOT NULL,
    intent_type VARCHAR(20) NOT NULL,
    contact_endpoint VARCHAR(512) NOT NULL,
    description TEXT NOT NULL,
    description_vector VECTOR(1024),  -- GLM-5: 1024 维度, OpenAI: 1536 维度
    tasks_requested INT DEFAULT 0 NOT NULL,
    tasks_provided INT DEFAULT 0 NOT NULL,
    last_active TIMESTAMP DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS ix_agent_profiles_agent_id ON agent_profiles(agent_id);
CREATE INDEX IF NOT EXISTS ix_agent_profiles_domain ON agent_profiles(domain);
CREATE INDEX IF NOT EXISTS ix_agent_profiles_intent_type ON agent_profiles(intent_type);
CREATE INDEX IF NOT EXISTS ix_agent_profiles_domain_intent ON agent_profiles(domain, intent_type);

-- 创建 HNSW 索引加速向量搜索
CREATE INDEX IF NOT EXISTS idx_agent_profiles_description_vector_hnsw
ON agent_profiles
USING hnsw (description_vector vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 插入一些测试数据 (GLM-5: 1024 维度)
INSERT INTO agent_profiles (agent_id, domain, intent_type, contact_endpoint, description, description_vector, tasks_provided) VALUES
('test_data_provider_01', 'finance', 'bid', 'https://example.com/webhook', '提供A股ETF历史数据和防御性资产波动率回测数据', '[0.1,0.2,0.3]' || repeat(',0.1', 1020), 42),
('test_text_formatter_01', 'education', 'bid', 'https://example.com/format', '专注文本清洗与Obsidian格式化，处理K-12英文阅读资料', '[0.2,0.1,0.4]' || repeat(',0.1', 1020), 15)
ON CONFLICT (agent_id) DO NOTHING;

-- 输出初始化完成信息
DO $$
BEGIN
    RAISE NOTICE 'Agent Hub Database initialized successfully!';
END $$;
