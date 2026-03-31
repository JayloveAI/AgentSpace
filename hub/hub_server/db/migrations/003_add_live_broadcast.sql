-- Migration 003: Ensure live status fields exist

DO $$ BEGIN
    CREATE TYPE node_status_enum AS ENUM ('active', 'busy', 'offline');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

ALTER TABLE agent_profiles
ADD COLUMN IF NOT EXISTS node_status node_status_enum DEFAULT 'offline' NOT NULL;

ALTER TABLE agent_profiles
ADD COLUMN IF NOT EXISTS live_broadcast VARCHAR(500) DEFAULT NULL;

ALTER TABLE agent_profiles
ADD COLUMN IF NOT EXISTS status_updated_at TIMESTAMP DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_agent_profiles_node_status
ON agent_profiles(node_status);

CREATE INDEX IF NOT EXISTS idx_agent_profiles_domain_status
ON agent_profiles(domain, node_status);
