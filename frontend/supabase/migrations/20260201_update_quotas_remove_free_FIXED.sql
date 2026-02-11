-- FIXED VERSION: Update user_quotas table to remove 'free' plan
-- This version updates data BEFORE changing constraints

-- STEP 1: Update existing problematic data first
-- Convert any 'free' plans to 'demo'
UPDATE user_quotas
SET 
  plan_type = 'demo',
  plan_name = 'Plano Demo',
  leads_limit = 5,
  campaigns_limit = 0,
  messages_limit = 0,
  plan_expires_at = NOW() + INTERVAL '7 days',
  updated_at = NOW()
WHERE plan_type = 'free';

-- Convert any other invalid plan types to 'demo'
UPDATE user_quotas
SET 
  plan_type = 'demo',
  plan_name = 'Plano Demo',
  leads_limit = 5,
  campaigns_limit = 0,
  messages_limit = 0,
  plan_expires_at = NOW() + INTERVAL '7 days',
  updated_at = NOW()
WHERE plan_type NOT IN ('demo', 'pro', 'enterprise');

-- STEP 2: Now it's safe to update the constraint
ALTER TABLE user_quotas 
  DROP CONSTRAINT IF EXISTS user_quotas_plan_type_check;

ALTER TABLE user_quotas
  ADD CONSTRAINT user_quotas_plan_type_check 
  CHECK (plan_type IN ('demo', 'pro', 'enterprise'));

-- STEP 3: Update the upgrade_user_plan function
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
  -- Set limits based on plan (removed 'free')
  CASE p_plan_type
    WHEN 'demo' THEN
      v_leads_limit := 5;
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
      -- Default to demo if invalid plan
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
    reset_date = CASE
      WHEN p_plan_type IN ('pro', 'enterprise') THEN CURRENT_DATE + INTERVAL '1 month'
      ELSE reset_date
    END,
    updated_at = NOW()
  WHERE user_id = p_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- STEP 4: Update check_user_quota function
CREATE OR REPLACE FUNCTION check_user_quota(
  p_user_id UUID,
  p_action VARCHAR
)
RETURNS JSONB AS $$
DECLARE
  v_quota RECORD;
BEGIN
  -- Get user quota
  SELECT * INTO v_quota
  FROM user_quotas
  WHERE user_id = p_user_id;
  
  IF NOT FOUND THEN
    RETURN jsonb_build_object(
      'allowed', false,
      'reason', 'Quota not found. Please contact support.',
      'plan_type', 'unknown'
    );
  END IF;
  
  -- Check if demo plan expired
  IF v_quota.plan_type = 'demo' AND v_quota.plan_expires_at < NOW() THEN
    RETURN jsonb_build_object(
      'allowed', false,
      'reason', 'Plano Demo expirado. Assine o plano Pro para continuar.',
      'plan_type', v_quota.plan_type,
      'expired', true
    );
  END IF;
  
  -- Check based on action
  IF p_action = 'lead_search' THEN
    IF v_quota.leads_limit = -1 THEN
      RETURN jsonb_build_object('allowed', true, 'unlimited', true);
    END IF;
    
    IF v_quota.leads_used >= v_quota.leads_limit THEN
      RETURN jsonb_build_object(
        'allowed', false,
        'reason', CASE 
          WHEN v_quota.plan_type = 'demo' THEN 'Limite de buscas atingido! Assine o plano Pro para buscas ilimitadas.'
          ELSE 'Limite de buscas atingido este mês.'
        END,
        'used', v_quota.leads_used,
        'limit', v_quota.leads_limit,
        'plan_type', v_quota.plan_type
      );
    END IF;
    
    RETURN jsonb_build_object(
      'allowed', true,
      'used', v_quota.leads_used,
      'limit', v_quota.leads_limit,
      'plan_type', v_quota.plan_type
    );
    
  ELSIF p_action = 'campaign_send' THEN
    IF v_quota.campaigns_limit = 0 THEN
      RETURN jsonb_build_object(
        'allowed', false,
        'reason', 'Disparador WhatsApp disponível apenas no Plano Pro. Faça upgrade!',
        'plan_type', v_quota.plan_type,
        'feature_blocked', true
      );
    END IF;
    
    IF v_quota.campaigns_limit = -1 THEN
      RETURN jsonb_build_object('allowed', true, 'unlimited', true);
    END IF;
    
    IF v_quota.campaigns_used >= v_quota.campaigns_limit THEN
      RETURN jsonb_build_object(
        'allowed', false,
        'reason', 'Limite de campanhas atingido.',
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
    
  ELSIF p_action = 'message_send' THEN
    IF v_quota.messages_limit = 0 THEN
      RETURN jsonb_build_object(
        'allowed', false,
        'reason', 'Envio de mensagens disponível apenas no Plano Pro.',
        'plan_type', v_quota.plan_type
      );
    END IF;
    
    IF v_quota.messages_limit = -1 THEN
      RETURN jsonb_build_object('allowed', true, 'unlimited', true);
    END IF;
    
    IF v_quota.messages_sent >= v_quota.messages_limit THEN
      RETURN jsonb_build_object(
        'allowed', false,
        'reason', 'Limite de mensagens atingido.',
        'used', v_quota.messages_sent,
        'limit', v_quota.messages_limit,
        'plan_type', v_quota.plan_type
      );
    END IF;
    
    RETURN jsonb_build_object(
      'allowed', true,
      'used', v_quota.messages_sent,
      'limit', v_quota.messages_limit
    );
  END IF;
  
  RETURN jsonb_build_object('allowed', false, 'reason', 'Invalid action');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- STEP 5: Update reset_monthly_quotas
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
    AND plan_type IN ('pro', 'enterprise'); -- Only reset paid plans
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION upgrade_user_plan IS 'Upgrade user plan - supports demo, pro, enterprise (free removed)';
COMMENT ON FUNCTION check_user_quota IS 'Check quota with helpful messages for demo users';
