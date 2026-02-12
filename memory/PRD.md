# Client4You - Product Requirements Document

## Original Problem Statement
Complete analysis of GitHub repository (`https://github.com/FelipeDSP/refine-client4you.git`) to identify and resolve problems, bugs, or inconsistencies for deployment on Coolify VPS.

User's specific requests:
1. Fix application preview loading issues
2. Verify and explain "IA agent + WAHA + n8n" integration
3. Ensure automatic WAHA webhook configuration on session creation
4. Improve new user welcome email flow
5. Adapt backend for existing n8n workflow compatibility

## Architecture

### Tech Stack
- **Backend:** FastAPI (Python)
- **Frontend:** React + Vite + TypeScript + TailwindCSS
- **Database:** Supabase (PostgreSQL)
- **Integrations:** WAHA (WhatsApp API), n8n (Workflow Automation), Kiwify (Payments), OpenAI

### Key Files
- `backend/server.py` - Main FastAPI application
- `backend/waha_service.py` - WAHA session management with automatic webhook config
- `backend/agent_service.py` - n8n integration for AI agent
- `backend/security_utils.py` - Authentication and security utilities
- `frontend/src/integrations/supabase/client.ts` - Supabase client configuration

### Data Flow: WAHA → Backend → n8n
1. WAHA receives WhatsApp message
2. WAHA sends webhook to `POST /api/webhook/waha`
3. Backend processes message via `agent_service.py`
4. Backend forwards to n8n webhook (if `N8N_WEBHOOK_URL` configured)

## What's Been Implemented

### Session 1 (Previous Agent)
- Fixed frontend `framer-motion` dependency
- Automatic WAHA webhook configuration on session creation
- Endpoint `/api/whatsapp/webhook/configure` for updating existing sessions
- Improved new user welcome email template
- n8n-compatible payload in `agent_service.py`
- Documentation: `backend/docs/GUIA_N8N_ADAPTACAO.md`
- Test script: `test_agent_flow.py`

### Session 2 (Current - 2026-02-12)
- Configured backend `.env` with Supabase credentials
- Backend now communicating correctly with Supabase
- Confirmed automatic webhook configuration is working

## Required Environment Variables

### Backend (.env)
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxx
SUPABASE_JWT_SECRET=xxx
WAHA_DEFAULT_URL=https://waha.xxx.com
WAHA_MASTER_KEY=xxx
BACKEND_WEBHOOK_URL=https://api.xxx.com  # IMPORTANT for WAHA webhook
N8N_WEBHOOK_URL=https://n8n.xxx.com/webhook/xxx  # For AI agent
CORS_ORIGINS=https://app.xxx.com
```

## Prioritized Backlog

### P0 - Critical
- [ ] User needs to configure `BACKEND_WEBHOOK_URL` in Coolify production
- [ ] User needs to configure `N8N_WEBHOOK_URL` for AI agent flow
- [ ] User needs to adapt n8n workflow per `GUIA_N8N_ADAPTACAO.md`

### P1 - Important
- [ ] Add `language` column to `agent_configs` table in Supabase (error in logs)
- [ ] Fix Dockerfile port inconsistencies (80 vs 3000)
- [ ] Replace fragile startup script with `supervisor`
- [ ] Remove duplicate `/app/temp_repo` directory

### P2 - Nice to Have
- [ ] Replace deprecated `datetime.utcnow()` with `datetime.now(timezone.utc)`
- [ ] Standardize environment variable names across docker-compose files
- [ ] Consolidate Docker setup (root Dockerfile vs subdirectory Dockerfiles)

## Known Issues
1. `agent_configs` table missing `language` column - causes save error
2. Duplicate `src/` directories in repository
3. Inconsistent Docker configurations between files
