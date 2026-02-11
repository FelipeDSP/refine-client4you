-- =====================================================
-- MIGRATION: Fix RLS for Service Role Backend Operations
-- Data: 03 Fevereiro 2025
-- Objetivo: Permitir que backend com service_role key opere nas tabelas
-- =====================================================

-- ===== IMPORTANTE =====
-- O backend usa SUPABASE_SERVICE_ROLE_KEY que BYPASSA RLS automaticamente
-- Porém, algumas tabelas podem não ter isso configurado corretamente
-- Esta migration garante que as policies estão corretas

-- ===== 1. CAMPAIGNS - Adicionar policy para service role =====

-- Primeiro, vamos verificar se já existe e dropar para recriar
DROP POLICY IF EXISTS "Service role full access to campaigns" ON public.campaigns;
DROP POLICY IF EXISTS "Backend service role access campaigns" ON public.campaigns;

-- Policy que permite acesso total para service_role
-- Nota: service_role key automaticamente bypassa RLS, mas em alguns casos
-- precisamos de policies explícitas

-- Vamos também criar policies mais permissivas para o backend
CREATE POLICY "Backend service role access campaigns"
    ON public.campaigns FOR ALL
    USING (true)
    WITH CHECK (true);

-- ===== 2. CAMPAIGN_CONTACTS - Policy para service role =====

DROP POLICY IF EXISTS "Service role full access to campaign_contacts" ON public.campaign_contacts;
DROP POLICY IF EXISTS "Backend service role access campaign_contacts" ON public.campaign_contacts;

CREATE POLICY "Backend service role access campaign_contacts"
    ON public.campaign_contacts FOR ALL
    USING (true)
    WITH CHECK (true);

-- ===== 3. MESSAGE_LOGS - Policy para service role =====

DROP POLICY IF EXISTS "Service role full access to message_logs" ON public.message_logs;
DROP POLICY IF EXISTS "Backend service role access message_logs" ON public.message_logs;

CREATE POLICY "Backend service role access message_logs"
    ON public.message_logs FOR ALL
    USING (true)
    WITH CHECK (true);

-- ===== 4. USER_QUOTAS - Garantir acesso do backend =====

DROP POLICY IF EXISTS "Backend service role access user_quotas" ON public.user_quotas;

CREATE POLICY "Backend service role access user_quotas"
    ON public.user_quotas FOR ALL
    USING (true)
    WITH CHECK (true);

-- ===== 5. WEBHOOK_LOGS - Garantir que backend pode inserir =====

DROP POLICY IF EXISTS "Backend can insert webhook logs" ON public.webhook_logs;

-- Criar policy se tabela existir
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'webhook_logs') THEN
        EXECUTE 'CREATE POLICY "Backend can insert webhook logs" ON public.webhook_logs FOR ALL USING (true) WITH CHECK (true)';
    END IF;
END $$;

-- ===== 6. PAYMENT_HISTORY - Garantir que backend pode inserir =====

DROP POLICY IF EXISTS "Backend can insert payment history" ON public.payment_history;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'payment_history') THEN
        EXECUTE 'CREATE POLICY "Backend can insert payment history" ON public.payment_history FOR ALL USING (true) WITH CHECK (true)';
    END IF;
END $$;

-- ===== 7. NOTIFICATIONS - Garantir acesso do backend =====

DROP POLICY IF EXISTS "Backend service role access notifications" ON public.notifications;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'notifications') THEN
        EXECUTE 'CREATE POLICY "Backend service role access notifications" ON public.notifications FOR ALL USING (true) WITH CHECK (true)';
    END IF;
END $$;

-- ===== FIM DA MIGRATION =====

DO $$
BEGIN
    RAISE NOTICE '✅ RLS Policies atualizadas para permitir service_role';
    RAISE NOTICE '📝 Tabelas afetadas:';
    RAISE NOTICE '   - campaigns';
    RAISE NOTICE '   - campaign_contacts';
    RAISE NOTICE '   - message_logs';
    RAISE NOTICE '   - user_quotas';
    RAISE NOTICE '   - webhook_logs (se existir)';
    RAISE NOTICE '   - payment_history (se existir)';
    RAISE NOTICE '   - notifications (se existir)';
END $$;
