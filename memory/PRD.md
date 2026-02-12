# Client4You - Product Requirements Document

## Original Problem Statement
Complete analysis of GitHub repository (`https://github.com/FelipeDSP/refine-client4you.git`) to identify and resolve problems, bugs, or inconsistencies for deployment on Coolify VPS.

User's specific requests:
1. Fix application preview loading issues
2. Verify and explain "IA agent + WAHA + n8n" integration
3. Ensure automatic WAHA webhook configuration on session creation
4. Improve new user welcome email flow
5. Adapt backend for existing n8n workflow compatibility
6. Each company configures their own OpenAI API key

## Architecture

### Tech Stack
- **Backend:** FastAPI (Python)
- **Frontend:** React + Vite + TypeScript + TailwindCSS
- **Database:** Supabase (PostgreSQL)
- **Integrations:** WAHA (WhatsApp API), n8n (Workflow Automation), Kiwify (Payments), OpenAI

### Key Files
- `backend/server.py` - Main FastAPI application
- `backend/waha_service.py` - WAHA session management with automatic webhook config
- `backend/agent_service.py` - n8n integration for AI agent (sends OpenAI credentials)
- `backend/security_utils.py` - Authentication and security utilities
- `frontend/src/pages/Settings.tsx` - Settings page with OpenAI configuration
- `frontend/src/pages/AgenteIA.tsx` - AI Agent page with config warning

### Data Flow: WAHA → Backend → n8n
1. WAHA receives WhatsApp message
2. WAHA sends webhook to `POST /api/webhook/waha`
3. Backend processes message via `agent_service.py`
4. Backend forwards to n8n webhook including OpenAI API key from company config
5. n8n uses dynamic API key to call OpenAI

## What's Been Implemented

### Session 1 (Previous Agent)
- Fixed frontend `framer-motion` dependency
- Automatic WAHA webhook configuration on session creation
- Endpoint `/api/whatsapp/webhook/configure` for updating existing sessions
- Improved new user welcome email template
- n8n-compatible payload in `agent_service.py`
- Documentation: `backend/docs/GUIA_N8N_ADAPTACAO.md`

### Session 2 (Current - 2026-02-12)
- ✅ Configured backend `.env` with Supabase credentials
- ✅ Fixed `waha_session` mapping in `company_settings` table
- ✅ Backend auto-saves session name when connecting WhatsApp
- ✅ Tested full flow: WAHA → Backend → n8n (working!)
- ✅ **OpenAI API Key per company**:
  - Added `openai_api_key`, `model`, `temperature` fields to `agent_configs`
  - Settings page now has OpenAI configuration in "Integrações" tab
  - AI Agent page shows warning if API key not configured
  - Backend sends API key in n8n payload for dynamic use

## Required Environment Variables

### Backend (.env)
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxx
SUPABASE_JWT_SECRET=xxx
WAHA_DEFAULT_URL=https://waha.xxx.com
WAHA_MASTER_KEY=xxx
BACKEND_WEBHOOK_URL=https://api.xxx.com
N8N_WEBHOOK_URL=https://webhook.xxx.com/webhook/iaagent.xxx
CORS_ORIGINS=https://app.xxx.com
```

## SQL Migrations Required

Execute in Supabase SQL Editor:
```sql
-- Migration 001: Add language column
ALTER TABLE public.agent_configs 
ADD COLUMN IF NOT EXISTS language text DEFAULT 'pt-BR';

-- Migration 002: Add OpenAI credentials
ALTER TABLE public.agent_configs 
ADD COLUMN IF NOT EXISTS openai_api_key text;

ALTER TABLE public.agent_configs 
ADD COLUMN IF NOT EXISTS model text DEFAULT 'gpt-4.1-mini';

ALTER TABLE public.agent_configs 
ADD COLUMN IF NOT EXISTS temperature numeric DEFAULT 0.7;
```

## n8n Payload Structure

The backend now sends this to n8n:
```json
{
  "payload": { /* original WAHA payload */ },
  "telefone_normalizado": "5511999999999",
  "texto_cliente": "message text",
  "variaveis": {
    "server_url": "https://waha.xxx.com",
    "instancia": "session_name",
    "api_key": "waha_api_key",
    "phone": "5511999999999",
    "mensagem": "message text"
  },
  "openai": {
    "api_key": "sk-...",
    "model": "gpt-4.1-mini",
    "temperature": 0.7
  },
  "client4you": {
    "company_id": "uuid",
    "company_name": "Company Name",
    "session_name": "session_name",
    "agent_config": { /* full config */ }
  },
  "event": "message",
  "session": "session_name",
  "sender": "5511999999999@c.us",
  "message_type": "text",
  "has_media": false
}
```

## Prioritized Backlog

### P0 - Critical (Done!)
- ✅ Backend communicating with Supabase
- ✅ WAHA webhook auto-configuration
- ✅ n8n integration working
- ✅ OpenAI credentials per company

### P1 - User Action Required
- [ ] Execute SQL migrations in Supabase
- [ ] Configure `BACKEND_WEBHOOK_URL` in Coolify production
- [ ] Adapt n8n workflow to use dynamic `openai.api_key`

### P2 - Nice to Have
- [ ] Fix Dockerfile port inconsistencies (80 vs 3000)
- [ ] Replace fragile startup script with `supervisor`
- [ ] Remove duplicate `/app/temp_repo` directory
- [ ] Replace deprecated `datetime.utcnow()` with `datetime.now(timezone.utc)`

## n8n Workflow Adaptation

To use dynamic OpenAI credentials, replace the "OpenAI Chat Model" node with an HTTP Request:

```javascript
// HTTP Request node configuration
{
  "method": "POST",
  "url": "https://api.openai.com/v1/chat/completions",
  "headers": {
    "Authorization": "Bearer {{ $('Webhook1').item.json.openai.api_key }}",
    "Content-Type": "application/json"
  },
  "body": {
    "model": "{{ $('Webhook1').item.json.openai.model }}",
    "temperature": {{ $('Webhook1').item.json.openai.temperature }},
    "messages": [
      {"role": "system", "content": "{{ $json.Prompt }}"},
      {"role": "user", "content": "{{ $('Junta_mensagens').item.json.todas_mensagens }}"}
    ]
  }
}
```
