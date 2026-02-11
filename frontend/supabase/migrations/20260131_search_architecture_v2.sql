-- ============================================
-- MIGRATION: Nova Arquitetura de Busca v2
-- Data: 31 Janeiro 2025
-- Objetivo: Deduplicação, Paginação, Biblioteca
-- ============================================

-- ===== 1. ATUALIZAR TABELA LEADS =====
-- Adicionar campos para deduplicação e rastreamento

ALTER TABLE public.leads 
ADD COLUMN IF NOT EXISTS fingerprint TEXT,
ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS times_found INTEGER DEFAULT 1,
ADD COLUMN IF NOT EXISTS sources JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT ARRAY[]::TEXT[],
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- Adicionar constraint unique no fingerprint por empresa
-- (permite mesmo lead em empresas diferentes)
CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_company_fingerprint 
ON public.leads(company_id, fingerprint) 
WHERE fingerprint IS NOT NULL;

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_leads_fingerprint ON public.leads(fingerprint) WHERE fingerprint IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_leads_last_seen ON public.leads(company_id, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_is_favorite ON public.leads(company_id, is_favorite) WHERE is_favorite = true;
CREATE INDEX IF NOT EXISTS idx_leads_times_found ON public.leads(company_id, times_found DESC);

-- Índice GIN para busca em arrays de tags
CREATE INDEX IF NOT EXISTS idx_leads_tags ON public.leads USING GIN(tags);

-- Comentários
COMMENT ON COLUMN public.leads.fingerprint IS 'Hash MD5 único: nome+endereço+telefone';
COMMENT ON COLUMN public.leads.times_found IS 'Número de vezes que este lead apareceu em buscas';
COMMENT ON COLUMN public.leads.sources IS 'Array de IDs de buscas onde este lead foi encontrado';
COMMENT ON COLUMN public.leads.is_favorite IS 'Lead marcado como favorito pelo usuário';
COMMENT ON COLUMN public.leads.tags IS 'Tags customizadas pelo usuário';

-- ===== 2. CRIAR TABELA SEARCH_SESSIONS =====
-- Controla sessões de busca com paginação

CREATE TABLE IF NOT EXISTS public.search_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    
    -- Tipo e parâmetros da busca
    search_type TEXT NOT NULL CHECK (search_type IN ('serp', 'cnae', 'manual')),
    query TEXT NOT NULL,
    location TEXT,
    filters JSONB DEFAULT '{}'::jsonb,
    
    -- Controle de paginação
    current_page INTEGER DEFAULT 0,
    results_per_page INTEGER DEFAULT 20,
    total_pages_available INTEGER,
    total_results_found INTEGER DEFAULT 0,
    
    -- Estatísticas
    new_leads_count INTEGER DEFAULT 0,
    duplicate_leads_count INTEGER DEFAULT 0,
    
    -- Status e timestamps
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'paused', 'error')),
    error_message TEXT,
    last_fetch_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Metadados adicionais
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Índices para search_sessions
CREATE INDEX IF NOT EXISTS idx_search_sessions_company ON public.search_sessions(company_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_search_sessions_user ON public.search_sessions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_search_sessions_status ON public.search_sessions(company_id, status);

-- Comentários
COMMENT ON TABLE public.search_sessions IS 'Sessões de busca com controle de paginação e estatísticas';
COMMENT ON COLUMN public.search_sessions.search_type IS 'Tipo: serp (Google Maps), cnae (Receita Federal), manual (importação)';
COMMENT ON COLUMN public.search_sessions.current_page IS 'Página atual (0-based)';
COMMENT ON COLUMN public.search_sessions.new_leads_count IS 'Total de leads novos encontrados nesta sessão';
COMMENT ON COLUMN public.search_sessions.duplicate_leads_count IS 'Total de duplicados ignorados nesta sessão';

-- ===== 3. ENABLE RLS =====
ALTER TABLE public.search_sessions ENABLE ROW LEVEL SECURITY;

-- ===== 4. RLS POLICIES - SEARCH_SESSIONS =====

-- Policy: SELECT (usuários veem sessões da própria empresa)
DROP POLICY IF EXISTS "Users can view own company search sessions" ON public.search_sessions;
CREATE POLICY "Users can view own company search sessions"
    ON public.search_sessions FOR SELECT
    USING (company_id = get_user_company_id(auth.uid()));

-- Policy: INSERT (usuários criam sessões na própria empresa)
DROP POLICY IF EXISTS "Users can insert own company search sessions" ON public.search_sessions;
CREATE POLICY "Users can insert own company search sessions"
    ON public.search_sessions FOR INSERT
    WITH CHECK (company_id = get_user_company_id(auth.uid()));

-- Policy: UPDATE (usuários atualizam sessões da própria empresa)
DROP POLICY IF EXISTS "Users can update own company search sessions" ON public.search_sessions;
CREATE POLICY "Users can update own company search sessions"
    ON public.search_sessions FOR UPDATE
    USING (company_id = get_user_company_id(auth.uid()));

-- Policy: DELETE (usuários deletam sessões da própria empresa)
DROP POLICY IF EXISTS "Users can delete own company search sessions" ON public.search_sessions;
CREATE POLICY "Users can delete own company search sessions"
    ON public.search_sessions FOR DELETE
    USING (company_id = get_user_company_id(auth.uid()));

-- ===== 5. ATUALIZAR RLS POLICIES - LEADS =====
-- Adicionar policy para UPDATE (permite marcar favoritos e tags)

DROP POLICY IF EXISTS "Users can update leads in their company" ON public.leads;
CREATE POLICY "Users can update leads in their company"
    ON public.leads FOR UPDATE
    USING (company_id = get_user_company_id(auth.uid()));

-- ===== 6. FUNÇÕES AUXILIARES =====

-- Função para gerar fingerprint (MD5)
CREATE OR REPLACE FUNCTION generate_lead_fingerprint(
    p_name TEXT,
    p_address TEXT,
    p_phone TEXT
) RETURNS TEXT AS $$
BEGIN
    RETURN md5(
        COALESCE(LOWER(TRIM(p_name)), '') || '|' ||
        COALESCE(LOWER(TRIM(p_address)), '') || '|' ||
        COALESCE(REGEXP_REPLACE(p_phone, '\D', '', 'g'), '')
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION generate_lead_fingerprint IS 'Gera hash MD5 único para identificar leads duplicados';

-- Função para atualizar leads existentes quando encontrados novamente
CREATE OR REPLACE FUNCTION update_existing_lead_on_duplicate(
    p_lead_id UUID,
    p_search_session_id UUID
) RETURNS VOID AS $$
BEGIN
    UPDATE public.leads
    SET 
        last_seen_at = NOW(),
        times_found = times_found + 1,
        sources = sources || jsonb_build_object('session_id', p_search_session_id, 'found_at', NOW())
    WHERE id = p_lead_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_existing_lead_on_duplicate IS 'Atualiza lead existente quando encontrado novamente em uma busca';

-- ===== 7. TRIGGER PARA AUTO-GERAR FINGERPRINT =====

-- Função trigger
CREATE OR REPLACE FUNCTION auto_generate_fingerprint()
RETURNS TRIGGER AS $$
BEGIN
    -- Só gera se fingerprint estiver vazio
    IF NEW.fingerprint IS NULL OR NEW.fingerprint = '' THEN
        NEW.fingerprint := generate_lead_fingerprint(NEW.name, NEW.address, NEW.phone);
    END IF;
    
    -- Garante que first_seen_at seja setado
    IF NEW.first_seen_at IS NULL THEN
        NEW.first_seen_at := NOW();
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Criar trigger
DROP TRIGGER IF EXISTS trigger_auto_generate_fingerprint ON public.leads;
CREATE TRIGGER trigger_auto_generate_fingerprint
    BEFORE INSERT OR UPDATE ON public.leads
    FOR EACH ROW
    EXECUTE FUNCTION auto_generate_fingerprint();

-- ===== 8. ATUALIZAR LEADS EXISTENTES (BACKFILL) =====
-- Gerar fingerprints para leads já existentes

UPDATE public.leads
SET 
    fingerprint = generate_lead_fingerprint(name, address, phone),
    first_seen_at = COALESCE(first_seen_at, created_at),
    last_seen_at = COALESCE(last_seen_at, created_at)
WHERE fingerprint IS NULL;

-- ===== 9. VIEWS ÚTEIS =====

-- View: Leads mais encontrados (populares)
CREATE OR REPLACE VIEW public.popular_leads AS
SELECT 
    l.*,
    l.times_found as popularity_score
FROM public.leads l
WHERE l.times_found > 1
ORDER BY l.times_found DESC, l.last_seen_at DESC;

COMMENT ON VIEW public.popular_leads IS 'Leads encontrados múltiplas vezes (potencialmente mais relevantes)';

-- View: Estatísticas por sessão de busca
CREATE OR REPLACE VIEW public.search_sessions_stats AS
SELECT 
    ss.id,
    ss.company_id,
    ss.search_type,
    ss.query,
    ss.location,
    ss.current_page,
    ss.new_leads_count,
    ss.duplicate_leads_count,
    ss.total_results_found,
    (ss.new_leads_count + ss.duplicate_leads_count) as total_processed,
    CASE 
        WHEN (ss.new_leads_count + ss.duplicate_leads_count) > 0 
        THEN ROUND((ss.new_leads_count::numeric / (ss.new_leads_count + ss.duplicate_leads_count)) * 100, 2)
        ELSE 0
    END as new_leads_percentage,
    ss.status,
    ss.created_at,
    ss.last_fetch_at
FROM public.search_sessions ss;

COMMENT ON VIEW public.search_sessions_stats IS 'Estatísticas agregadas por sessão de busca';

-- ===== 10. GRANTS (PERMISSÕES) =====

-- Garantir que usuários autenticados possam acessar as funções
GRANT EXECUTE ON FUNCTION generate_lead_fingerprint TO authenticated;
GRANT EXECUTE ON FUNCTION update_existing_lead_on_duplicate TO authenticated;

-- Permitir SELECT nas views
GRANT SELECT ON public.popular_leads TO authenticated;
GRANT SELECT ON public.search_sessions_stats TO authenticated;

-- ===== FIM DA MIGRATION =====

-- Verificações finais
DO $$
BEGIN
    RAISE NOTICE '✅ Migration 20260131_search_architecture_v2 completed successfully!';
    RAISE NOTICE '📊 Tables updated: leads (new columns), search_sessions (new table)';
    RAISE NOTICE '🔧 Functions created: generate_lead_fingerprint, update_existing_lead_on_duplicate';
    RAISE NOTICE '🔐 RLS policies applied';
    RAISE NOTICE '📈 Indexes created for performance';
END $$;
