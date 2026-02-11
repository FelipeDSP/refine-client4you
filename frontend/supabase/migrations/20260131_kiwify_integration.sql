-- =====================================================
-- MIGRATION: Kiwify Integration & Security
-- Data: 31 Janeiro 2025
-- Objetivo: Webhook Kiwify + Validação de Assinaturas
-- =====================================================

-- ===== 1. ATUALIZAR TABELA USER_QUOTAS =====
-- Adicionar campos para controle de assinatura

ALTER TABLE public.user_quotas
ADD COLUMN IF NOT EXISTS subscription_id TEXT,
ADD COLUMN IF NOT EXISTS order_id TEXT,
ADD COLUMN IF NOT EXISTS subscription_status TEXT DEFAULT 'inactive' CHECK (subscription_status IN ('active', 'canceled', 'expired', 'inactive')),
ADD COLUMN IF NOT EXISTS cancellation_reason TEXT,
ADD COLUMN IF NOT EXISTS last_payment_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS next_billing_date DATE;

-- Índices
CREATE INDEX IF NOT EXISTS idx_user_quotas_subscription_id ON public.user_quotas(subscription_id);
CREATE INDEX IF NOT EXISTS idx_user_quotas_subscription_status ON public.user_quotas(subscription_status);

-- Comentários
COMMENT ON COLUMN public.user_quotas.subscription_id IS 'ID da assinatura no Kiwify';
COMMENT ON COLUMN public.user_quotas.order_id IS 'ID do pedido no Kiwify';
COMMENT ON COLUMN public.user_quotas.subscription_status IS 'Status: active, canceled, expired, inactive';
COMMENT ON COLUMN public.user_quotas.cancellation_reason IS 'Motivo do cancelamento';

-- ===== 2. CRIAR TABELA WEBHOOK_LOGS =====
-- Armazena logs de todos os webhooks recebidos (auditoria)

CREATE TABLE IF NOT EXISTS public.webhook_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('success', 'failed', 'ignored')),
    error_message TEXT,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_webhook_logs_event_type ON public.webhook_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_status ON public.webhook_logs(status);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_created_at ON public.webhook_logs(created_at DESC);

-- Comentários
COMMENT ON TABLE public.webhook_logs IS 'Log de todos os webhooks recebidos (Kiwify)';
COMMENT ON COLUMN public.webhook_logs.event_type IS 'Tipo do evento: order.paid, order.refunded, subscription.canceled';
COMMENT ON COLUMN public.webhook_logs.payload IS 'Payload completo do webhook';
COMMENT ON COLUMN public.webhook_logs.status IS 'Status do processamento: success, failed, ignored';

-- RLS
ALTER TABLE public.webhook_logs ENABLE ROW LEVEL SECURITY;

-- Policy: Apenas admins podem ver logs
CREATE POLICY "Only admins can view webhook logs"
    ON public.webhook_logs FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM public.profiles
        WHERE id = auth.uid() AND role = 'admin'
    ));

-- ===== 3. CRIAR TABELA PAYMENT_HISTORY =====
-- Histórico de pagamentos para referência

CREATE TABLE IF NOT EXISTS public.payment_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    company_id UUID REFERENCES public.companies(id) ON DELETE SET NULL,
    
    -- Dados do pagamento
    order_id TEXT NOT NULL,
    subscription_id TEXT,
    product_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    
    -- Valores
    amount NUMERIC(10,2) NOT NULL,
    currency TEXT DEFAULT 'BRL',
    
    -- Status
    payment_status TEXT NOT NULL CHECK (payment_status IN ('paid', 'refunded', 'canceled', 'pending')),
    payment_method TEXT,
    
    -- Plano associado
    plan_name TEXT NOT NULL,
    plan_period TEXT DEFAULT 'monthly',
    
    -- Datas
    paid_at TIMESTAMP WITH TIME ZONE,
    refunded_at TIMESTAMP WITH TIME ZONE,
    canceled_at TIMESTAMP WITH TIME ZONE,
    
    -- Metadados
    metadata JSONB DEFAULT '{}'::jsonb,
    
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_payment_history_user_id ON public.payment_history(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_history_company_id ON public.payment_history(company_id);
CREATE INDEX IF NOT EXISTS idx_payment_history_order_id ON public.payment_history(order_id);
CREATE INDEX IF NOT EXISTS idx_payment_history_subscription_id ON public.payment_history(subscription_id);
CREATE INDEX IF NOT EXISTS idx_payment_history_payment_status ON public.payment_history(payment_status);

-- Comentários
COMMENT ON TABLE public.payment_history IS 'Histórico de pagamentos (Kiwify)';
COMMENT ON COLUMN public.payment_history.payment_status IS 'Status: paid, refunded, canceled, pending';

-- RLS
ALTER TABLE public.payment_history ENABLE ROW LEVEL SECURITY;

-- Policy: Usuários veem próprio histórico
CREATE POLICY "Users can view own payment history"
    ON public.payment_history FOR SELECT
    USING (user_id = auth.uid());

-- Policy: Admins veem tudo
CREATE POLICY "Admins can view all payment history"
    ON public.payment_history FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM public.profiles
        WHERE id = auth.uid() AND role = 'admin'
    ));

-- ===== 4. FUNÇÃO: VERIFICAR ASSINATURA ATIVA =====

CREATE OR REPLACE FUNCTION check_subscription_active(p_user_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_quota RECORD;
BEGIN
    SELECT * INTO v_quota
    FROM public.user_quotas
    WHERE user_id = p_user_id;
    
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;
    
    -- Verificar se assinatura está ativa E não expirou
    IF v_quota.subscription_status = 'active' AND 
       (v_quota.valid_until IS NULL OR v_quota.valid_until > NOW()) THEN
        RETURN TRUE;
    END IF;
    
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION check_subscription_active IS 'Verifica se usuário tem assinatura ativa e válida';

-- ===== 5. FUNÇÃO: AUTO-EXPIRAR ASSINATURAS =====

CREATE OR REPLACE FUNCTION expire_subscriptions()
RETURNS INTEGER AS $$
DECLARE
    v_expired_count INTEGER;
BEGIN
    -- Marcar assinaturas expiradas
    UPDATE public.user_quotas
    SET 
        subscription_status = 'expired',
        plan = 'Demo',
        lead_search_limit = 5,
        campaigns_limit = 0,
        updated_at = NOW()
    WHERE 
        subscription_status = 'active' 
        AND valid_until < NOW()
        AND valid_until IS NOT NULL;
    
    GET DIAGNOSTICS v_expired_count = ROW_COUNT;
    
    RETURN v_expired_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION expire_subscriptions IS 'Expira assinaturas vencidas (rodar diariamente via cron)';

-- ===== 6. TRIGGER: AUTO-UPDATE timestamp =====

CREATE OR REPLACE FUNCTION update_payment_history_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_payment_history_timestamp ON public.payment_history;
CREATE TRIGGER trigger_update_payment_history_timestamp
    BEFORE UPDATE ON public.payment_history
    FOR EACH ROW
    EXECUTE FUNCTION update_payment_history_timestamp();

-- ===== 7. VIEW: ASSINATURAS ATIVAS =====

CREATE OR REPLACE VIEW public.active_subscriptions AS
SELECT 
    uq.user_id,
    uq.company_id,
    uq.plan,
    uq.subscription_id,
    uq.subscription_status,
    uq.valid_until,
    p.email,
    p.full_name,
    c.name as company_name,
    CASE 
        WHEN uq.valid_until IS NULL THEN TRUE
        WHEN uq.valid_until > NOW() THEN TRUE
        ELSE FALSE
    END as is_valid
FROM public.user_quotas uq
LEFT JOIN public.profiles p ON p.id = uq.user_id
LEFT JOIN public.companies c ON c.id = uq.company_id
WHERE uq.subscription_status = 'active';

COMMENT ON VIEW public.active_subscriptions IS 'View com todas as assinaturas ativas';

-- ===== 8. GRANTS =====

GRANT SELECT ON public.active_subscriptions TO authenticated;
GRANT EXECUTE ON FUNCTION check_subscription_active TO authenticated;

-- ===== 9. CONFIGURAÇÕES INICIAIS =====

-- Marcar usuários existentes como 'inactive' se não tiverem subscription_id
UPDATE public.user_quotas
SET subscription_status = 'inactive'
WHERE subscription_id IS NULL AND subscription_status IS NULL;

-- ===== FIM DA MIGRATION =====

DO $$
BEGIN
    RAISE NOTICE '✅ Migration Kiwify Integration completed successfully!';
    RAISE NOTICE '📊 Tables: webhook_logs, payment_history';
    RAISE NOTICE '🔧 Functions: check_subscription_active, expire_subscriptions';
    RAISE NOTICE '🔐 RLS policies applied';
    RAISE NOTICE '📈 Views: active_subscriptions';
    RAISE NOTICE '';
    RAISE NOTICE '📝 PRÓXIMOS PASSOS:';
    RAISE NOTICE '1. Configurar KIWIFY_WEBHOOK_SECRET no backend/.env';
    RAISE NOTICE '2. Adicionar IDs dos produtos no kiwify_webhook.py';
    RAISE NOTICE '3. Configurar webhook no painel Kiwify apontando para:';
    RAISE NOTICE '   https://seu-dominio.com/api/webhook/kiwify';
    RAISE NOTICE '4. Configurar cron job para rodar expire_subscriptions() diariamente';
END $$;
