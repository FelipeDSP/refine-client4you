-- Create agent_configs table for AI agent configuration per company
CREATE TABLE IF NOT EXISTS public.agent_configs (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  enabled BOOLEAN NOT NULL DEFAULT false,
  name TEXT NOT NULL DEFAULT 'Assistente Virtual',
  personality TEXT DEFAULT '',
  system_prompt TEXT DEFAULT '',
  welcome_message TEXT DEFAULT '',
  response_delay INTEGER NOT NULL DEFAULT 3,
  max_response_length INTEGER NOT NULL DEFAULT 500,
  tone TEXT NOT NULL DEFAULT 'professional',
  language TEXT NOT NULL DEFAULT 'pt-BR',
  auto_qualify BOOLEAN NOT NULL DEFAULT true,
  qualification_questions JSONB DEFAULT '[]'::jsonb,
  blocked_topics JSONB DEFAULT '[]'::jsonb,
  working_hours JSONB DEFAULT '{"enabled": false, "start": "09:00", "end": "18:00", "timezone": "America/Sao_Paulo"}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  CONSTRAINT unique_agent_config_company UNIQUE (company_id)
);

-- Enable RLS
ALTER TABLE public.agent_configs ENABLE ROW LEVEL SECURITY;

-- Users can view their own company's agent config
CREATE POLICY "Users can view their company agent config"
ON public.agent_configs
FOR SELECT
USING (
  company_id = get_user_company_id(auth.uid())
);

-- Users can insert their company's agent config
CREATE POLICY "Users can insert their company agent config"
ON public.agent_configs
FOR INSERT
WITH CHECK (
  company_id = get_user_company_id(auth.uid())
);

-- Users can update their company's agent config
CREATE POLICY "Users can update their company agent config"
ON public.agent_configs
FOR UPDATE
USING (
  company_id = get_user_company_id(auth.uid())
);

-- Service role bypass for backend operations
CREATE POLICY "Service role full access to agent_configs"
ON public.agent_configs
FOR ALL
USING (auth.role() = 'service_role');

-- Trigger for updated_at
CREATE TRIGGER update_agent_configs_updated_at
BEFORE UPDATE ON public.agent_configs
FOR EACH ROW
EXECUTE FUNCTION public.handle_updated_at();
