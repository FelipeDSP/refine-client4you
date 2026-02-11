-- =====================================================
-- SECURITY ENHANCEMENTS MIGRATION
-- Data: 2026-02-07
-- Descrição: Adiciona tabelas para sistema anti-brute force,
--            2FA, logs de auditoria e whitelist de IPs
-- =====================================================

-- =====================================================
-- 1. TABELA: login_attempts (Tentativas de Login)
-- =====================================================
CREATE TABLE IF NOT EXISTS public.login_attempts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT NOT NULL,
  ip_address TEXT NOT NULL,
  user_agent TEXT,
  success BOOLEAN NOT NULL DEFAULT false,
  failure_reason TEXT,
  turnstile_token TEXT,
  turnstile_valid BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  -- Índices para performance
  CONSTRAINT login_attempts_email_idx CHECK (char_length(email) <= 255)
);

-- Índices para busca rápida
CREATE INDEX IF NOT EXISTS idx_login_attempts_email ON public.login_attempts(email);
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON public.login_attempts(ip_address);
CREATE INDEX IF NOT EXISTS idx_login_attempts_created ON public.login_attempts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_login_attempts_email_created ON public.login_attempts(email, created_at DESC);

-- RLS: Apenas admins podem ver logs de login
ALTER TABLE public.login_attempts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Super admins podem ver todos os login attempts"
  ON public.login_attempts
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.user_roles
      WHERE user_roles.user_id = auth.uid()
      AND user_roles.role = 'super_admin'
    )
  );

-- =====================================================
-- 2. TABELA: user_2fa (Configurações 2FA)
-- =====================================================
CREATE TABLE IF NOT EXISTS public.user_2fa (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  secret TEXT NOT NULL, -- Secret TOTP (criptografado no app)
  enabled BOOLEAN NOT NULL DEFAULT false,
  backup_codes TEXT[], -- Códigos de backup (hashed)
  last_used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  -- Garante 1 configuração por usuário
  CONSTRAINT user_2fa_user_id_unique UNIQUE(user_id)
);

-- Índice
CREATE INDEX IF NOT EXISTS idx_user_2fa_user_id ON public.user_2fa(user_id);

-- RLS: Usuários só podem ver/editar seu próprio 2FA
ALTER TABLE public.user_2fa ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Usuários podem gerenciar seu próprio 2FA"
  ON public.user_2fa
  FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Admins podem ver 2FA de todos"
  ON public.user_2fa
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.user_roles
      WHERE user_roles.user_id = auth.uid()
      AND user_roles.role = 'super_admin'
    )
  );

-- =====================================================
-- 3. TABELA: audit_logs (Logs de Auditoria Admin)
-- =====================================================
CREATE TABLE IF NOT EXISTS public.audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  user_email TEXT NOT NULL,
  action TEXT NOT NULL, -- 'user_deleted', 'user_role_changed', 'company_deleted', 'quota_updated'
  target_type TEXT NOT NULL, -- 'user', 'company', 'quota'
  target_id UUID,
  target_email TEXT, -- Email do usuário afetado
  details JSONB, -- Detalhes adicionais da ação
  ip_address TEXT,
  user_agent TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  -- Constraints
  CONSTRAINT audit_logs_action_check CHECK (char_length(action) <= 100),
  CONSTRAINT audit_logs_target_type_check CHECK (target_type IN ('user', 'company', 'quota', 'role', 'settings'))
);

-- Índices para busca rápida
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON public.audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON public.audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_target_type ON public.audit_logs(target_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON public.audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_target_id ON public.audit_logs(target_id);

-- RLS: Apenas super admins podem ver logs de auditoria
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Super admins podem ver todos os audit logs"
  ON public.audit_logs
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.user_roles
      WHERE user_roles.user_id = auth.uid()
      AND user_roles.role = 'super_admin'
    )
  );

CREATE POLICY "Super admins podem inserir audit logs"
  ON public.audit_logs
  FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.user_roles
      WHERE user_roles.user_id = auth.uid()
      AND user_roles.role = 'super_admin'
    )
  );

-- =====================================================
-- 4. TABELA: ip_whitelist (Whitelist de IPs por Empresa)
-- =====================================================
CREATE TABLE IF NOT EXISTS public.ip_whitelist (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  ip_address TEXT NOT NULL,
  description TEXT, -- Descrição do IP (ex: "Escritório São Paulo")
  enabled BOOLEAN NOT NULL DEFAULT true,
  created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  -- Garante IPs únicos por empresa
  CONSTRAINT ip_whitelist_company_ip_unique UNIQUE(company_id, ip_address),
  CONSTRAINT ip_whitelist_ip_format CHECK (ip_address ~ '^([0-9]{1,3}\.){3}[0-9]{1,3}(/[0-9]{1,2})?$')
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_ip_whitelist_company_id ON public.ip_whitelist(company_id);
CREATE INDEX IF NOT EXISTS idx_ip_whitelist_enabled ON public.ip_whitelist(enabled);

-- RLS: Apenas company owners e admins podem gerenciar
ALTER TABLE public.ip_whitelist ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Company owners podem gerenciar IP whitelist"
  ON public.ip_whitelist
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles
      WHERE profiles.id = auth.uid()
      AND profiles.company_id = ip_whitelist.company_id
    )
    AND (
      EXISTS (
        SELECT 1 FROM public.user_roles
        WHERE user_roles.user_id = auth.uid()
        AND user_roles.role IN ('company_owner', 'super_admin')
      )
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.profiles
      WHERE profiles.id = auth.uid()
      AND profiles.company_id = ip_whitelist.company_id
    )
    AND (
      EXISTS (
        SELECT 1 FROM public.user_roles
        WHERE user_roles.user_id = auth.uid()
        AND user_roles.role IN ('company_owner', 'super_admin')
      )
    )
  );

CREATE POLICY "Admins podem ver todos os IP whitelists"
  ON public.ip_whitelist
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.user_roles
      WHERE user_roles.user_id = auth.uid()
      AND user_roles.role = 'super_admin'
    )
  );

-- =====================================================
-- 5. FUNÇÃO: Limpar tentativas antigas (> 7 dias)
-- =====================================================
CREATE OR REPLACE FUNCTION public.cleanup_old_login_attempts()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  DELETE FROM public.login_attempts
  WHERE created_at < now() - interval '7 days';
END;
$$;

-- =====================================================
-- 6. FUNÇÃO: Limpar logs de auditoria antigos (> 90 dias)
-- =====================================================
CREATE OR REPLACE FUNCTION public.cleanup_old_audit_logs()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  DELETE FROM public.audit_logs
  WHERE created_at < now() - interval '90 days';
END;
$$;

-- =====================================================
-- 7. COMENTÁRIOS NAS TABELAS
-- =====================================================
COMMENT ON TABLE public.login_attempts IS 'Registra todas as tentativas de login (sucesso e falha) para prevenção de brute force';
COMMENT ON TABLE public.user_2fa IS 'Armazena configurações de autenticação de dois fatores (TOTP) dos usuários';
COMMENT ON TABLE public.audit_logs IS 'Registra todas as ações administrativas críticas para auditoria';
COMMENT ON TABLE public.ip_whitelist IS 'Lista de IPs permitidos por empresa para acesso restrito';

-- =====================================================
-- FIM DA MIGRATION
-- =====================================================
