-- Create user_quotas table
CREATE TABLE IF NOT EXISTS user_quotas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
  
  -- Plan Info
  plan_type VARCHAR(20) DEFAULT 'demo' CHECK (plan_type IN ('demo', 'free', 'pro', 'enterprise')),
  plan_name VARCHAR(50),
  
  -- Lead Search Limits
  leads_limit INTEGER DEFAULT 5,
  leads_used INTEGER DEFAULT 0,
  
  -- Campaign/Message Limits
  campaigns_limit INTEGER DEFAULT 0, -- 0 = bloqueado, -1 = ilimitado
  campaigns_used INTEGER DEFAULT 0,
  
  messages_limit INTEGER DEFAULT 0, -- 0 = bloqueado, -1 = ilimitado
  messages_sent INTEGER DEFAULT 0,
  
  -- Control
  reset_date DATE DEFAULT (CURRENT_DATE + INTERVAL '1 month'),
  plan_expires_at TIMESTAMPTZ, -- Para demo: 7 dias
  
  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster queries
CREATE INDEX idx_user_quotas_user_id ON user_quotas(user_id);
CREATE INDEX idx_user_quotas_plan_type ON user_quotas(plan_type);
CREATE INDEX idx_user_quotas_reset_date ON user_quotas(reset_date);

-- RLS Policies
ALTER TABLE user_quotas ENABLE ROW LEVEL SECURITY;

-- Users can view their own quotas
CREATE POLICY "Users can view own quotas"
  ON user_quotas FOR SELECT
  USING (auth.uid() = user_id);

-- Users can update their own quotas (for increments)
CREATE POLICY "Users can update own quotas"
  ON user_quotas FOR UPDATE
  USING (auth.uid() = user_id);

-- System can insert quotas (via service role or authenticated)
CREATE POLICY "System can insert quotas"
  ON user_quotas FOR INSERT
  WITH CHECK (true);

-- Function to create default quota for new user
CREATE OR REPLACE FUNCTION create_default_quota()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO user_quotas (user_id, company_id, plan_type, plan_name, leads_limit, plan_expires_at)
  VALUES (
    NEW.id, 
    NULL, -- company_id será preenchido depois
    'demo',
    'Plano Demo',
    5,
    NOW() + INTERVAL '7 days'
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to create quota when user is created
DROP TRIGGER IF EXISTS on_auth_user_created_quota ON auth.users;
CREATE TRIGGER on_auth_user_created_quota
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION create_default_quota();

-- Function to reset monthly quotas
CREATE OR REPLACE FUNCTION reset_monthly_quotas()
RETURNS void AS $$
BEGIN
  UPDATE user_quotas
  SET 
    leads_used = 0,
    campaigns_used = 0,
    messages_sent = 0,
    reset_date = CURRENT_DATE + INTERVAL '1 month',
    updated_at = NOW()
  WHERE reset_date <= CURRENT_DATE
    AND plan_type IN ('free', 'pro', 'enterprise');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check if user can perform action
CREATE OR REPLACE FUNCTION check_user_quota(
  p_user_id UUID,
  p_action VARCHAR -- 'lead_search', 'campaign_send', 'message_send'
)
RETURNS JSONB AS $$
DECLARE
  v_quota RECORD;
  v_result JSONB;
BEGIN
  -- Get user quota
  SELECT * INTO v_quota
  FROM user_quotas
  WHERE user_id = p_user_id;
  
  IF NOT FOUND THEN
    RETURN jsonb_build_object(
      'allowed', false,
      'reason', 'Quota not found'
    );
  END IF;
  
  -- Check if demo plan expired
  IF v_quota.plan_type = 'demo' AND v_quota.plan_expires_at < NOW() THEN
    RETURN jsonb_build_object(
      'allowed', false,
      'reason', 'Demo plan expired',
      'plan_type', v_quota.plan_type
    );
  END IF;
  
  -- Check based on action
  IF p_action = 'lead_search' THEN
    IF v_quota.leads_limit = -1 THEN -- Unlimited
      RETURN jsonb_build_object('allowed', true, 'unlimited', true);
    END IF;
    
    IF v_quota.leads_used >= v_quota.leads_limit THEN
      RETURN jsonb_build_object(
        'allowed', false,
        'reason', 'Lead search limit reached',
        'used', v_quota.leads_used,
        'limit', v_quota.leads_limit,
        'plan_type', v_quota.plan_type
      );
    END IF;
    
    RETURN jsonb_build_object(
      'allowed', true,
      'used', v_quota.leads_used,
      'limit', v_quota.leads_limit
    );
    
  ELSIF p_action = 'campaign_send' THEN
    IF v_quota.campaigns_limit = 0 THEN
      RETURN jsonb_build_object(
        'allowed', false,
        'reason', 'Campaigns blocked on current plan',
        'plan_type', v_quota.plan_type
      );
    END IF;
    
    IF v_quota.campaigns_limit = -1 THEN -- Unlimited
      RETURN jsonb_build_object('allowed', true, 'unlimited', true);
    END IF;
    
    IF v_quota.campaigns_used >= v_quota.campaigns_limit THEN
      RETURN jsonb_build_object(
        'allowed', false,
        'reason', 'Campaign limit reached',
        'used', v_quota.campaigns_used,
        'limit', v_quota.campaigns_limit,
        'plan_type', v_quota.plan_type
      );
    END IF;
    
    RETURN jsonb_build_object(
      'allowed', true,
      'used', v_quota.campaigns_used,
      'limit', v_quota.campaigns_limit
    );
  END IF;
  
  RETURN jsonb_build_object('allowed', false, 'reason', 'Unknown action');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to increment quota usage
CREATE OR REPLACE FUNCTION increment_quota_usage(
  p_user_id UUID,
  p_action VARCHAR,
  p_amount INTEGER DEFAULT 1
)
RETURNS void AS $$
BEGIN
  IF p_action = 'lead_search' THEN
    UPDATE user_quotas
    SET leads_used = leads_used + p_amount, updated_at = NOW()
    WHERE user_id = p_user_id;
    
  ELSIF p_action = 'campaign_send' THEN
    UPDATE user_quotas
    SET campaigns_used = campaigns_used + p_amount, updated_at = NOW()
    WHERE user_id = p_user_id;
    
  ELSIF p_action = 'message_send' THEN
    UPDATE user_quotas
    SET messages_sent = messages_sent + p_amount, updated_at = NOW()
    WHERE user_id = p_user_id;
  END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to upgrade user plan
CREATE OR REPLACE FUNCTION upgrade_user_plan(
  p_user_id UUID,
  p_plan_type VARCHAR,
  p_plan_name VARCHAR
)
RETURNS void AS $$
DECLARE
  v_leads_limit INTEGER;
  v_campaigns_limit INTEGER;
  v_messages_limit INTEGER;
BEGIN
  -- Set limits based on plan
  CASE p_plan_type
    WHEN 'demo' THEN
      v_leads_limit := 5;
      v_campaigns_limit := 0;
      v_messages_limit := 0;
    WHEN 'free' THEN
      v_leads_limit := 50;
      v_campaigns_limit := 0;
      v_messages_limit := 0;
    WHEN 'pro' THEN
      v_leads_limit := -1; -- Unlimited
      v_campaigns_limit := -1;
      v_messages_limit := -1;
    WHEN 'enterprise' THEN
      v_leads_limit := -1;
      v_campaigns_limit := -1;
      v_messages_limit := -1;
    ELSE
      v_leads_limit := 5;
      v_campaigns_limit := 0;
      v_messages_limit := 0;
  END CASE;
  
  UPDATE user_quotas
  SET 
    plan_type = p_plan_type,
    plan_name = p_plan_name,
    leads_limit = v_leads_limit,
    campaigns_limit = v_campaigns_limit,
    messages_limit = v_messages_limit,
    plan_expires_at = CASE 
      WHEN p_plan_type = 'demo' THEN NOW() + INTERVAL '7 days'
      ELSE NULL
    END,
    updated_at = NOW()
  WHERE user_id = p_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON TABLE user_quotas IS 'User plan quotas and usage limits for SaaS model';
