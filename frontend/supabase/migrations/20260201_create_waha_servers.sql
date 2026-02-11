-- Create waha_servers table for multi-server architecture
CREATE TABLE IF NOT EXISTS waha_servers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- Server Info
  name VARCHAR(100) NOT NULL UNIQUE,
  url VARCHAR(255) NOT NULL,
  api_key TEXT NOT NULL,
  
  -- Capacity & Load Balancing
  max_instances INTEGER DEFAULT 50,
  current_instances INTEGER DEFAULT 0,
  
  -- Status
  status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'maintenance', 'offline')),
  health_status VARCHAR(20) DEFAULT 'unknown' CHECK (health_status IN ('healthy', 'degraded', 'unhealthy', 'unknown')),
  last_health_check TIMESTAMPTZ,
  
  -- Priority (lower = higher priority)
  priority INTEGER DEFAULT 100,
  
  -- Metadata
  region VARCHAR(50), -- 'us-east', 'sa-east', etc.
  notes TEXT,
  
  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create waha_instances table to track which company uses which server
CREATE TABLE IF NOT EXISTS waha_instances (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- Company/Session Info
  company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
  session_name VARCHAR(100) NOT NULL UNIQUE,
  
  -- Server Assignment
  server_id UUID REFERENCES waha_servers(id) ON DELETE SET NULL,
  
  -- Instance Status
  status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'starting', 'connected', 'disconnected', 'error')),
  connection_status TEXT,
  
  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  connected_at TIMESTAMPTZ,
  disconnected_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_waha_servers_status ON waha_servers(status);
CREATE INDEX idx_waha_servers_priority ON waha_servers(priority);
CREATE INDEX idx_waha_instances_company ON waha_instances(company_id);
CREATE INDEX idx_waha_instances_server ON waha_instances(server_id);
CREATE INDEX idx_waha_instances_status ON waha_instances(status);

-- RLS Policies
ALTER TABLE waha_servers ENABLE ROW LEVEL SECURITY;
ALTER TABLE waha_instances ENABLE ROW LEVEL SECURITY;

-- Only service role can manage servers (admin only)
CREATE POLICY "Service role can manage servers"
  ON waha_servers FOR ALL
  USING (true);

-- Users can view their own instances
CREATE POLICY "Users can view own instances"
  ON waha_instances FOR SELECT
  USING (
    company_id IN (
      SELECT company_id FROM profiles WHERE id = auth.uid()
    )
  );

-- Function to get next available server (load balancing)
CREATE OR REPLACE FUNCTION get_next_available_waha_server()
RETURNS UUID AS $$
DECLARE
  v_server_id UUID;
BEGIN
  -- Get server with:
  -- 1. Active status
  -- 2. Healthy or unknown health
  -- 3. Not at max capacity
  -- 4. Lowest priority number (highest priority)
  -- 5. Fewest current instances (load balancing)
  SELECT id INTO v_server_id
  FROM waha_servers
  WHERE status = 'active'
    AND health_status IN ('healthy', 'unknown')
    AND current_instances < max_instances
  ORDER BY 
    priority ASC,
    current_instances ASC,
    created_at ASC
  LIMIT 1;
  
  RETURN v_server_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to increment server instance count
CREATE OR REPLACE FUNCTION increment_server_instances(
  p_server_id UUID
)
RETURNS void AS $$
BEGIN
  UPDATE waha_servers
  SET 
    current_instances = current_instances + 1,
    updated_at = NOW()
  WHERE id = p_server_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to decrement server instance count
CREATE OR REPLACE FUNCTION decrement_server_instances(
  p_server_id UUID
)
RETURNS void AS $$
BEGIN
  UPDATE waha_servers
  SET 
    current_instances = GREATEST(0, current_instances - 1),
    updated_at = NOW()
  WHERE id = p_server_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to update server counts when instance is created
CREATE OR REPLACE FUNCTION update_server_count_on_instance_change()
RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    -- Increment count on new instance
    IF NEW.server_id IS NOT NULL THEN
      PERFORM increment_server_instances(NEW.server_id);
    END IF;
    RETURN NEW;
    
  ELSIF TG_OP = 'UPDATE' THEN
    -- If server changed, update both old and new
    IF OLD.server_id IS DISTINCT FROM NEW.server_id THEN
      IF OLD.server_id IS NOT NULL THEN
        PERFORM decrement_server_instances(OLD.server_id);
      END IF;
      IF NEW.server_id IS NOT NULL THEN
        PERFORM increment_server_instances(NEW.server_id);
      END IF;
    END IF;
    RETURN NEW;
    
  ELSIF TG_OP = 'DELETE' THEN
    -- Decrement count on delete
    IF OLD.server_id IS NOT NULL THEN
      PERFORM decrement_server_instances(OLD.server_id);
    END IF;
    RETURN OLD;
  END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER waha_instance_server_count_trigger
  AFTER INSERT OR UPDATE OR DELETE ON waha_instances
  FOR EACH ROW
  EXECUTE FUNCTION update_server_count_on_instance_change();

-- Insert default WAHA server (current one)
INSERT INTO waha_servers (name, url, api_key, max_instances, priority, region, notes)
VALUES (
  'Primary Server',
  'https://waha.chatyou.chat',
  'PJ1X_5sPM2cgeAI3LB_ALOUPUyUkg9GjKvMZ7Leifi0',
  50,
  1,
  'default',
  'Servidor WAHA principal - configurado inicialmente'
)
ON CONFLICT (name) DO NOTHING;

COMMENT ON TABLE waha_servers IS 'WAHA servers for load balancing and multi-server support';
COMMENT ON TABLE waha_instances IS 'WhatsApp instances assigned to companies';
