-- Atomic quota increment function to prevent race conditions
-- Instead of read-then-write in Python, this does SET used = used + amount in a single SQL statement

CREATE OR REPLACE FUNCTION increment_quota_atomic(
  p_user_id UUID,
  p_field TEXT,
  p_amount INT DEFAULT 1
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  allowed_fields TEXT[] := ARRAY['campaigns_used', 'messages_used', 'leads_used', 'messages_sent'];
BEGIN
  -- Validate field name to prevent SQL injection
  IF NOT (p_field = ANY(allowed_fields)) THEN
    RAISE EXCEPTION 'Invalid field name: %', p_field;
  END IF;

  -- Atomic increment using dynamic SQL with validated field
  EXECUTE format(
    'UPDATE user_quotas SET %I = COALESCE(%I, 0) + $1 WHERE user_id = $2',
    p_field, p_field
  ) USING p_amount, p_user_id;

  RETURN FOUND;
END;
$$;

-- Atomic campaign counter increment to prevent race conditions in campaign_worker
CREATE OR REPLACE FUNCTION increment_campaign_counter_atomic(
  p_campaign_id UUID,
  p_field TEXT,
  p_amount INT DEFAULT 1
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  allowed_fields TEXT[] := ARRAY['sent_count', 'error_count', 'pending_count'];
BEGIN
  -- Validate field name to prevent SQL injection
  IF NOT (p_field = ANY(allowed_fields)) THEN
    RAISE EXCEPTION 'Invalid field name: %', p_field;
  END IF;

  -- Atomic increment using dynamic SQL with validated field
  EXECUTE format(
    'UPDATE campaigns SET %I = COALESCE(%I, 0) + $1, updated_at = NOW() WHERE id = $2',
    p_field, p_field
  ) USING p_amount, p_campaign_id;

  RETURN FOUND;
END;
$$;
