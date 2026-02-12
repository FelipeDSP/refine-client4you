-- =====================================================
-- Client4You - Migration para adicionar OpenAI API Key
-- Execute este SQL no Supabase SQL Editor
-- =====================================================

-- Adicionar coluna 'openai_api_key' para cada empresa configurar sua própria chave
ALTER TABLE public.agent_configs 
ADD COLUMN IF NOT EXISTS openai_api_key text;

-- Adicionar coluna 'model' para escolher o modelo (gpt-4, gpt-4-turbo, gpt-3.5-turbo, etc)
ALTER TABLE public.agent_configs 
ADD COLUMN IF NOT EXISTS model text DEFAULT 'gpt-4.1-mini';

-- Adicionar coluna 'temperature' para controlar criatividade
ALTER TABLE public.agent_configs 
ADD COLUMN IF NOT EXISTS temperature numeric DEFAULT 0.7;

-- Comentários
COMMENT ON COLUMN public.agent_configs.openai_api_key IS 'Chave API da OpenAI do cliente';
COMMENT ON COLUMN public.agent_configs.model IS 'Modelo OpenAI: gpt-4.1-mini, gpt-4, gpt-3.5-turbo';
COMMENT ON COLUMN public.agent_configs.temperature IS 'Temperatura do modelo (0-1)';

-- Verificar
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'agent_configs' 
AND column_name IN ('openai_api_key', 'model', 'temperature');
