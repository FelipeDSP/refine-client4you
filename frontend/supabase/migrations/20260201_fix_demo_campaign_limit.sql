-- Fix Demo plan to allow 1 campaign for testing
-- Update the upgrade_user_plan function
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
      v_campaigns_limit := 1; -- Changed from 0 to 1
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
      -- Default to demo if invalid plan
      v_leads_limit := 5;
      v_campaigns_limit := 1;
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
    reset_date = CASE
      WHEN p_plan_type IN ('pro', 'enterprise') THEN CURRENT_DATE + INTERVAL '1 month'
      ELSE reset_date
    END,
    updated_at = NOW()
  WHERE user_id = p_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update create_default_quota function to include campaigns_limit
CREATE OR REPLACE FUNCTION create_default_quota()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO user_quotas (
    user_id, 
    company_id, 
    plan_type, 
    plan_name, 
    leads_limit,
    campaigns_limit,
    messages_limit,
    plan_expires_at
  )
  VALUES (
    NEW.id, 
    NULL, -- company_id será preenchido depois
    'demo',
    'Plano Demo',
    5,
    1,  -- 1 campaign for testing
    0,  -- No messages (need Pro)
    NOW() + INTERVAL '7 days'
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update existing demo users to have 1 campaign
UPDATE user_quotas
SET 
  campaigns_limit = 1,
  updated_at = NOW()
WHERE plan_type = 'demo' 
  AND campaigns_limit = 0;

COMMENT ON FUNCTION upgrade_user_plan IS 'Upgrade user plan - Demo now allows 1 campaign for testing';
