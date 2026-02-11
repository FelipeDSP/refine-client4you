-- ===============================================
-- REMOVER SCHEMA DO PROSPECTA IA
-- Mantém as tabelas originais intactas
-- ===============================================

-- 1. Remover triggers primeiro
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP TRIGGER IF EXISTS update_companies_updated_at ON public.companies;
DROP TRIGGER IF EXISTS update_profiles_updated_at ON public.profiles;
DROP TRIGGER IF EXISTS update_subscriptions_updated_at ON public.subscriptions;
DROP TRIGGER IF EXISTS update_leads_updated_at ON public.leads;

-- 2. Remover índices
DROP INDEX IF EXISTS idx_profiles_company_id;
DROP INDEX IF EXISTS idx_user_roles_user_id;
DROP INDEX IF EXISTS idx_user_roles_company_id;
DROP INDEX IF EXISTS idx_search_history_company_id;
DROP INDEX IF EXISTS idx_search_history_created_at;
DROP INDEX IF EXISTS idx_leads_company_id;
DROP INDEX IF EXISTS idx_leads_search_id;
DROP INDEX IF EXISTS idx_leads_created_at;

-- 3. Remover tabelas (ordem importa por causa das foreign keys)
DROP TABLE IF EXISTS public.leads CASCADE;
DROP TABLE IF EXISTS public.search_history CASCADE;
DROP TABLE IF EXISTS public.subscriptions CASCADE;
DROP TABLE IF EXISTS public.user_roles CASCADE;
DROP TABLE IF EXISTS public.profiles CASCADE;
DROP TABLE IF EXISTS public.companies CASCADE;

-- 4. Remover funções
DROP FUNCTION IF EXISTS public.handle_new_user();
DROP FUNCTION IF EXISTS public.update_updated_at_column();
DROP FUNCTION IF EXISTS public.has_role(UUID, app_role);
DROP FUNCTION IF EXISTS public.user_belongs_to_company(UUID, UUID);
DROP FUNCTION IF EXISTS public.get_user_company_id(UUID);

-- 5. Remover tipos (enums)
DROP TYPE IF EXISTS public.app_role;
DROP TYPE IF EXISTS public.subscription_plan;