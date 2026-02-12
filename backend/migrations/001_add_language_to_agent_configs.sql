-- =====================================================
-- Client4You - Migration para agent_configs
-- Execute este SQL no Supabase SQL Editor
-- =====================================================

-- Adicionar coluna 'language' que estava faltando
ALTER TABLE public.agent_configs 
ADD COLUMN IF NOT EXISTS language text DEFAULT 'pt-BR';

-- Adicionar coluna 'qualification_questions' (array de perguntas para qualificação)
ALTER TABLE public.agent_configs 
ADD COLUMN IF NOT EXISTS qualification_questions jsonb DEFAULT '[]'::jsonb;

-- Comentário explicativo
COMMENT ON COLUMN public.agent_configs.language IS 'Idioma do agente: pt-BR, en-US, es-ES';
COMMENT ON COLUMN public.agent_configs.qualification_questions IS 'Perguntas para qualificação de leads pelo agente';

-- Verificar se a migration foi aplicada
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'agent_configs' 
AND column_name IN ('language', 'qualification_questions');
