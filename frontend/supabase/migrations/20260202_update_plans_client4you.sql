-- Update plans for Client4you rebranding
-- New plans: demo, basico, intermediario, avancado

-- Update constraint to accept new plan types
ALTER TABLE user_quotas 
  DROP CONSTRAINT IF EXISTS user_quotas_plan_type_check;

ALTER TABLE user_quotas
  ADD CONSTRAINT user_quotas_plan_type_check 
  CHECK (plan_type IN ('demo', 'basico', 'intermediario', 'avancado'));

-- Update existing 'pro' and 'enterprise' plans to new structure
UPDATE user_quotas
SET 
  plan_type = 'intermediario',
  plan_name = 'Plano Intermediário',
  updated_at = NOW()
WHERE plan_type = 'pro';

UPDATE user_quotas
SET 
  plan_type = 'avancado',
  plan_name = 'Plano Avançado',
  updated_at = NOW()
WHERE plan_type = 'enterprise';

-- Update upgrade_user_plan function with new plans
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
      v_campaigns_limit := 1;
      v_messages_limit := 0;
    WHEN 'basico' THEN
      v_leads_limit := -1; -- Unlimited
      v_campaigns_limit := 0; -- No campaigns
      v_messages_limit := 0;
    WHEN 'intermediario' THEN
      v_leads_limit := -1; -- Unlimited
      v_campaigns_limit := -1; -- Unlimited
      v_messages_limit := -1;
    WHEN 'avancado' THEN
      v_leads_limit := -1; -- Unlimited
      v_campaigns_limit := -1; -- Unlimited
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
      WHEN p_plan_type IN ('basico', 'intermediario', 'avancado') THEN CURRENT_DATE + INTERVAL '1 month'
      ELSE reset_date
    END,
    updated_at = NOW()
  WHERE user_id = p_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update check_user_quota function with new plan names
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
      'reason', 'Plano Demo expirado. Assine o plano Básico ou superior para continuar.',
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
          WHEN v_quota.plan_type = 'demo' THEN 'Limite de buscas atingido! Assine um plano para buscas ilimitadas.'
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
        'reason', 'Disparador WhatsApp disponível nos planos Intermediário e Avançado. Faça upgrade!',
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
        'reason', 'Envio de mensagens disponível nos planos Intermediário e Avançado.',
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

-- Update reset_monthly_quotas
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
    AND plan_type IN ('basico', 'intermediario', 'avancado');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION upgrade_user_plan IS 'Upgrade user plan - Client4you plans: demo, basico, intermediario, avancado';
COMMENT ON FUNCTION check_user_quota IS 'Check quota with helpful messages for Client4you users';
