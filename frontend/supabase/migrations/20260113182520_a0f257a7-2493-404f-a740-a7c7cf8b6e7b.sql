-- ============================================
-- SCHEMA COMPLETO PARA SAAS MULTI-TENANT
-- ============================================

-- 1. ENUM DE PAPÉIS (roles separados para segurança)
CREATE TYPE public.app_role AS ENUM ('super_admin', 'company_owner', 'admin', 'member');

-- 2. TABELA DE EMPRESAS
CREATE TABLE public.companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- 3. TABELA DE PERFIS (vinculada a auth.users e companies)
CREATE TABLE public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    company_id UUID REFERENCES public.companies(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- 4. TABELA DE ROLES (SEPARADA para segurança - evita privilege escalation)
CREATE TABLE public.user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    role app_role NOT NULL DEFAULT 'member',
    company_id UUID REFERENCES public.companies(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    UNIQUE (user_id, role, company_id)
);

-- 5. TABELA DE ASSINATURAS
CREATE TABLE public.subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES public.companies(id) ON DELETE CASCADE NOT NULL UNIQUE,
    plan_id TEXT NOT NULL DEFAULT 'demo',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled', 'expired')),
    demo_used BOOLEAN DEFAULT false,
    current_period_start TIMESTAMP WITH TIME ZONE DEFAULT now(),
    current_period_end TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- 6. TABELA DE HISTÓRICO DE BUSCAS
CREATE TABLE public.search_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES public.companies(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    query TEXT NOT NULL,
    location TEXT NOT NULL,
    results_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- 7. TABELA DE LEADS
CREATE TABLE public.leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES public.companies(id) ON DELETE CASCADE NOT NULL,
    search_id UUID REFERENCES public.search_history(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    website TEXT,
    address TEXT,
    has_whatsapp BOOLEAN DEFAULT false,
    has_email BOOLEAN DEFAULT false,
    rating NUMERIC(2,1),
    reviews_count INTEGER DEFAULT 0,
    category TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- ============================================
-- HABILITAR ROW LEVEL SECURITY EM TODAS AS TABELAS
-- ============================================
ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.search_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;

-- ============================================
-- FUNÇÃO SECURITY DEFINER PARA VERIFICAR ROLES
-- ============================================
CREATE OR REPLACE FUNCTION public.has_role(_user_id UUID, _role app_role)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.user_roles
    WHERE user_id = _user_id
      AND role = _role
  )
$$;

-- Função para obter company_id do usuário
CREATE OR REPLACE FUNCTION public.get_user_company_id(_user_id UUID)
RETURNS UUID
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT company_id
  FROM public.profiles
  WHERE id = _user_id
$$;

-- ============================================
-- POLÍTICAS RLS PARA COMPANIES
-- ============================================
CREATE POLICY "Users can view their own company"
ON public.companies FOR SELECT
TO authenticated
USING (id = public.get_user_company_id(auth.uid()));

CREATE POLICY "Company owners can update their company"
ON public.companies FOR UPDATE
TO authenticated
USING (id = public.get_user_company_id(auth.uid()) AND public.has_role(auth.uid(), 'company_owner'));

-- ============================================
-- POLÍTICAS RLS PARA PROFILES
-- ============================================
CREATE POLICY "Users can view own profile"
ON public.profiles FOR SELECT
TO authenticated
USING (id = auth.uid());

CREATE POLICY "Users can update own profile"
ON public.profiles FOR UPDATE
TO authenticated
USING (id = auth.uid());

CREATE POLICY "Users can view profiles from same company"
ON public.profiles FOR SELECT
TO authenticated
USING (company_id = public.get_user_company_id(auth.uid()));

-- ============================================
-- POLÍTICAS RLS PARA USER_ROLES
-- ============================================
CREATE POLICY "Users can view own roles"
ON public.user_roles FOR SELECT
TO authenticated
USING (user_id = auth.uid());

CREATE POLICY "Company owners can manage roles in their company"
ON public.user_roles FOR ALL
TO authenticated
USING (
  company_id = public.get_user_company_id(auth.uid()) 
  AND public.has_role(auth.uid(), 'company_owner')
);

-- ============================================
-- POLÍTICAS RLS PARA SUBSCRIPTIONS
-- ============================================
CREATE POLICY "Users can view their company subscription"
ON public.subscriptions FOR SELECT
TO authenticated
USING (company_id = public.get_user_company_id(auth.uid()));

CREATE POLICY "Company owners can update subscription"
ON public.subscriptions FOR UPDATE
TO authenticated
USING (
  company_id = public.get_user_company_id(auth.uid()) 
  AND public.has_role(auth.uid(), 'company_owner')
);

-- ============================================
-- POLÍTICAS RLS PARA SEARCH_HISTORY
-- ============================================
CREATE POLICY "Users can view their company search history"
ON public.search_history FOR SELECT
TO authenticated
USING (company_id = public.get_user_company_id(auth.uid()));

CREATE POLICY "Users can create search history for their company"
ON public.search_history FOR INSERT
TO authenticated
WITH CHECK (company_id = public.get_user_company_id(auth.uid()));

CREATE POLICY "Users can delete their company search history"
ON public.search_history FOR DELETE
TO authenticated
USING (company_id = public.get_user_company_id(auth.uid()));

-- ============================================
-- POLÍTICAS RLS PARA LEADS
-- ============================================
CREATE POLICY "Users can view their company leads"
ON public.leads FOR SELECT
TO authenticated
USING (company_id = public.get_user_company_id(auth.uid()));

CREATE POLICY "Users can create leads for their company"
ON public.leads FOR INSERT
TO authenticated
WITH CHECK (company_id = public.get_user_company_id(auth.uid()));

CREATE POLICY "Users can delete their company leads"
ON public.leads FOR DELETE
TO authenticated
USING (company_id = public.get_user_company_id(auth.uid()));

-- ============================================
-- TRIGGERS PARA UPDATED_AT
-- ============================================
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TRIGGER on_companies_updated
  BEFORE UPDATE ON public.companies
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER on_profiles_updated
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER on_subscriptions_updated
  BEFORE UPDATE ON public.subscriptions
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ============================================
-- TRIGGER PARA CRIAR PERFIL AUTOMATICAMENTE NO SIGNUP
-- ============================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  new_company_id UUID;
BEGIN
  -- Criar empresa para o novo usuário
  INSERT INTO public.companies (name, slug)
  VALUES (
    COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1)),
    NEW.id::text
  )
  RETURNING id INTO new_company_id;

  -- Criar perfil
  INSERT INTO public.profiles (id, email, full_name, company_id)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1)),
    new_company_id
  );

  -- Atribuir role de company_owner
  INSERT INTO public.user_roles (user_id, role, company_id)
  VALUES (NEW.id, 'company_owner', new_company_id);

  -- Criar assinatura demo
  INSERT INTO public.subscriptions (company_id, plan_id, status)
  VALUES (new_company_id, 'demo', 'active');

  RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ============================================
-- ÍNDICES PARA PERFORMANCE
-- ============================================
CREATE INDEX idx_profiles_company_id ON public.profiles(company_id);
CREATE INDEX idx_user_roles_user_id ON public.user_roles(user_id);
CREATE INDEX idx_user_roles_company_id ON public.user_roles(company_id);
CREATE INDEX idx_search_history_company_id ON public.search_history(company_id);
CREATE INDEX idx_leads_company_id ON public.leads(company_id);
CREATE INDEX idx_leads_search_id ON public.leads(search_id);