-- Migration 002: Add V1.5 Live Status Fields
-- This migration adds dual status fields for AgentHub V1.5
-- - node_status: Machine state for SQL filtering (active/busy/offline)
-- - live_broadcast: Human-readable status message for vector embedding
--
-- Run this migration on existing databases to upgrade to V1.5

-- Create enum type for node_status
DO $$ BEGIN
    CREATE TYPE node_status_enum AS ENUM ('active', 'busy', 'offline');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Add node_status column (machine state for SQL filtering)
ALTER TABLE agent_profiles
ADD COLUMN IF NOT EXISTS node_status node_status_enum DEFAULT 'offline' NOT NULL;

-- Add live_broadcast column (human-readable message for embedding)
ALTER TABLE agent_profiles
ADD COLUMN IF NOT EXISTS live_broadcast VARCHAR(500) DEFAULT NULL;

-- Add status_updated_at column
ALTER TABLE agent_profiles
ADD COLUMN IF NOT EXISTS status_updated_at TIMESTAMP DEFAULT NOW();

-- Create index on node_status for fast filtering
CREATE INDEX IF NOT EXISTS idx_agent_profiles_node_status
ON agent_profiles(node_status);

-- Create composite index on (domain, node_status) for hybrid search
CREATE INDEX IF NOT EXISTS idx_agent_profiles_domain_status
ON agent_profiles(domain, node_status);

-- Update existing agents to have 'active' status
UPDATE agent_profiles
SET node_status = 'active', status_updated_at = NOW()
WHERE node_status = 'offline';

-- Verify migration
SELECT
    column_name,
    data_type,
    column_default
FROM information_schema.columns
WHERE table_name = 'agent_profiles'
  AND column_name IN ('node_status', 'live_broadcast', 'status_updated_at')
ORDER BY ordinal_position;
