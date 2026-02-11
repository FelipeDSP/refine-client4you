-- ===============================================
-- ProspectaIA Database Schema
-- NÃO modifica tabelas existentes (Chatyou_*, João_*, Romilto_*)
-- ===============================================

-- 1. Enum para roles de usuário
CREATE TYPE public.app_role AS ENUM ('super_admin', 'company_owner', 'admin', 'member');

-- 2. Enum para plano de assinatura
CREATE TYPE public.subscription_plan AS ENUM ('demo', 'starter', 'professional', 'enterprise');

-- 3. Tabela de Empresas (multi-tenant)
CREATE TABLE public.companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    logo_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;

-- 4. Tabela de Perfis de Usuário
CREATE TABLE public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    company_id UUID REFERENCES public.companies(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- 5. Tabela de Roles de Usuário (separada para segurança)
CREATE TABLE public.user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    role app_role NOT NULL DEFAULT 'member',
    company_id UUID REFERENCES public.companies(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    UNIQUE (user_id, company_id)
);

ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;

-- 6. Tabela de Créditos/Assinatura
CREATE TABLE public.subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES public.companies(id) ON DELETE CASCADE NOT NULL UNIQUE,
    plan subscription_plan NOT NULL DEFAULT 'demo',
    credits_remaining INTEGER NOT NULL DEFAULT 10,
    credits_monthly_limit INTEGER NOT NULL DEFAULT 10,
    is_active BOOLEAN NOT NULL DEFAULT true,
    trial_used BOOLEAN NOT NULL DEFAULT false,
    current_period_start TIMESTAMP WITH TIME ZONE DEFAULT now(),
    current_period_end TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;

-- 7. Tabela de Histórico de Buscas
CREATE TABLE public.search_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES public.companies(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    query TEXT NOT NULL,
    location TEXT,
    category TEXT,
    results_count INTEGER DEFAULT 0,
    credits_used INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

ALTER TABLE public.search_history ENABLE ROW LEVEL SECURITY;

-- 8. Tabela de Leads
CREATE TABLE public.leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES public.companies(id) ON DELETE CASCADE NOT NULL,
    search_id UUID REFERENCES public.search_history(id) ON DELETE SET NULL,
    empresa TEXT NOT NULL,
    telefone TEXT,
    email TEXT,
    site TEXT,
    rating TEXT,
    review_count TEXT,
    especialidades TEXT,
    endereco TEXT,
    has_whatsapp BOOLEAN DEFAULT false,
    has_email BOOLEAN DEFAULT false,
    status TEXT DEFAULT 'novo',
    resumo_lead TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;

-- ===============================================
-- FUNÇÕES DE SEGURANÇA
-- ===============================================

-- Função para verificar role do usuário
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

-- Função para verificar se usuário pertence a uma empresa
CREATE OR REPLACE FUNCTION public.user_belongs_to_company(_user_id UUID, _company_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.profiles
    WHERE id = _user_id
      AND company_id = _company_id
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

-- ===============================================
-- TRIGGER: Criar perfil automaticamente no signup
-- ===============================================

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.profiles (id, email, full_name)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1))
  );
  RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ===============================================
-- TRIGGER: Atualizar updated_at automaticamente
-- ===============================================

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TRIGGER update_companies_updated_at
  BEFORE UPDATE ON public.companies
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_profiles_updated_at
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_subscriptions_updated_at
  BEFORE UPDATE ON public.subscriptions
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_leads_updated_at
  BEFORE UPDATE ON public.leads
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ===============================================
-- RLS POLICIES
-- ===============================================

-- Companies: usuários podem ver sua própria empresa
CREATE POLICY "Users can view their own company"
  ON public.companies FOR SELECT
  USING (public.user_belongs_to_company(auth.uid(), id));

CREATE POLICY "Company owners can update their company"
  ON public.companies FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM public.user_roles
      WHERE user_id = auth.uid()
        AND company_id = companies.id
        AND role IN ('company_owner', 'super_admin')
    )
  );

-- Profiles: usuários podem ver e editar seu próprio perfil
CREATE POLICY "Users can view own profile"
  ON public.profiles FOR SELECT
  USING (id = auth.uid());

CREATE POLICY "Users can view profiles in same company"
  ON public.profiles FOR SELECT
  USING (company_id = public.get_user_company_id(auth.uid()));

CREATE POLICY "Users can update own profile"
  ON public.profiles FOR UPDATE
  USING (id = auth.uid());

-- User Roles: apenas admins podem gerenciar
CREATE POLICY "Users can view own role"
  ON public.user_roles FOR SELECT
  USING (user_id = auth.uid());

CREATE POLICY "Admins can manage roles in their company"
  ON public.user_roles FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.user_roles ur
      WHERE ur.user_id = auth.uid()
        AND ur.company_id = user_roles.company_id
        AND ur.role IN ('company_owner', 'admin', 'super_admin')
    )
  );

-- Subscriptions: empresa pode ver sua assinatura
CREATE POLICY "Company members can view subscription"
  ON public.subscriptions FOR SELECT
  USING (public.user_belongs_to_company(auth.uid(), company_id));

CREATE POLICY "Company owners can manage subscription"
  ON public.subscriptions FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.user_roles
      WHERE user_id = auth.uid()
        AND company_id = subscriptions.company_id
        AND role IN ('company_owner', 'super_admin')
    )
  );

-- Search History: empresa pode ver seu histórico
CREATE POLICY "Company members can view search history"
  ON public.search_history FOR SELECT
  USING (public.user_belongs_to_company(auth.uid(), company_id));

CREATE POLICY "Company members can create searches"
  ON public.search_history FOR INSERT
  WITH CHECK (public.user_belongs_to_company(auth.uid(), company_id));

CREATE POLICY "Company admins can delete search history"
  ON public.search_history FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM public.user_roles
      WHERE user_id = auth.uid()
        AND company_id = search_history.company_id
        AND role IN ('company_owner', 'admin', 'super_admin')
    )
  );

-- Leads: empresa pode gerenciar seus leads
CREATE POLICY "Company members can view leads"
  ON public.leads FOR SELECT
  USING (public.user_belongs_to_company(auth.uid(), company_id));

CREATE POLICY "Company members can create leads"
  ON public.leads FOR INSERT
  WITH CHECK (public.user_belongs_to_company(auth.uid(), company_id));

CREATE POLICY "Company members can update leads"
  ON public.leads FOR UPDATE
  USING (public.user_belongs_to_company(auth.uid(), company_id));

CREATE POLICY "Company admins can delete leads"
  ON public.leads FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM public.user_roles
      WHERE user_id = auth.uid()
        AND company_id = leads.company_id
        AND role IN ('company_owner', 'admin', 'super_admin')
    )
  );

-- ===============================================
-- ÍNDICES PARA PERFORMANCE
-- ===============================================

CREATE INDEX idx_profiles_company_id ON public.profiles(company_id);
CREATE INDEX idx_user_roles_user_id ON public.user_roles(user_id);
CREATE INDEX idx_user_roles_company_id ON public.user_roles(company_id);
CREATE INDEX idx_search_history_company_id ON public.search_history(company_id);
CREATE INDEX idx_search_history_created_at ON public.search_history(created_at DESC);
CREATE INDEX idx_leads_company_id ON public.leads(company_id);
CREATE INDEX idx_leads_search_id ON public.leads(search_id);
CREATE INDEX idx_leads_created_at ON public.leads(created_at DESC);