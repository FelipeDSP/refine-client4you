from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import time as time_module
import pandas as pd
import io
import uuid
from pydantic import BaseModel, Field  # Importante para os endpoints

from models import (
    Campaign, CampaignCreate, CampaignUpdate, CampaignStatus, CampaignStats, CampaignWithStats,
    Contact, ContactStatus, MessageLog, CampaignSettings, CampaignMessage
)
from waha_service import WahaService
from supabase_service import get_supabase_service, SupabaseService
from campaign_worker import (
    start_campaign_worker, stop_campaign_worker, is_campaign_running
)
from security_utils import (
    get_authenticated_user,
    require_role,
    validate_file_upload,
    sanitize_csv_value,
    handle_error,
    validate_campaign_ownership,
    validate_quota_for_action
)
from kiwify_webhook import webhook_router
from admin_endpoints import admin_router
from security_endpoints import security_router
from agent_service import process_waha_message_for_n8n

# --- CORREÇÃO DO LOAD DOTENV ---
CURRENT_DIR = Path(__file__).parent
dotenv_path = CURRENT_DIR / '.env'
if not dotenv_path.exists():
    dotenv_path = CURRENT_DIR.parent / '.env'

load_dotenv(dotenv_path)
# -------------------------------

# Create the main app
app = FastAPI(title="Lead Dispatcher API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"❌ Validation error on {request.url}: {exc.errors()}")
    logger.error(f"Body: {exc.body}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body}
    )

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ========== Helper Functions ==========
def get_db() -> SupabaseService:
    """Get Supabase service instance"""
    return get_supabase_service()


# ========== In-memory cache for session names (Problem 3 fix) ==========
# Cache: company_id -> (session_name, timestamp)
_session_name_cache: dict[str, tuple[str, float]] = {}
_SESSION_CACHE_TTL = 300  # 5 minutes


async def get_session_name_for_company(company_id: str, company_name: str = None) -> str:
    """
    Define o nome da sessão do WhatsApp de forma segura.
    Formato: nome_empresa_id (ex: "acme_corp_efdaca5d")
    Uses in-memory cache with 5-minute TTL to avoid repeated DB queries.
    """
    import re

    # Check cache first
    if company_id in _session_name_cache:
        cached_name, cached_time = _session_name_cache[company_id]
        if (time_module.time() - cached_time) < _SESSION_CACHE_TTL:
            return cached_name

    logger.info(f"Buscando sessão para company_id: {company_id} (cache miss)")

    session_name = None
    try:
        db = get_db()
        config = await db.get_waha_config(company_id)

        if config and config.get("session_name"):
            session_name = config.get("session_name")
            logger.info(f"Usando sessão do banco: {session_name}")
        else:
            if not company_name:
                try:
                    company_result = db.client.table('companies')\
                        .select('name')\
                        .eq('id', company_id)\
                        .single()\
                        .execute()
                    if company_result.data:
                        company_name = company_result.data.get('name')
                except Exception as e:
                    logger.warning(f"Não encontrou nome da empresa: {e}")

            if company_name:
                safe_name = re.sub(r'[^a-zA-Z0-9]', '_', company_name.lower())
                safe_name = re.sub(r'_+', '_', safe_name).strip('_')[:30]
                short_id = company_id.split('-')[0] if company_id else 'unknown'
                session_name = f"{safe_name}_{short_id}"
            else:
                session_name = f"company_{company_id.split('-')[0] if company_id else 'unknown'}"
                logger.warning(f"Usando fallback: {session_name}")

    except Exception as e:
        logger.warning(f"Usando sessão padrão devido a erro: {e}")
        session_name = f"company_{company_id.split('-')[0] if company_id else 'unknown'}"

    # Store in cache
    _session_name_cache[company_id] = (session_name, time_module.time())
    return session_name


def calculate_campaign_stats(campaign: dict) -> CampaignStats:
    total = campaign.get("total_contacts", 0)
    sent = campaign.get("sent_count", 0)
    errors = campaign.get("error_count", 0)
    pending = campaign.get("pending_count", 0)
    
    progress = (sent / total * 100) if total > 0 else 0
    
    return CampaignStats(
        total=total,
        sent=sent,
        pending=pending,
        errors=errors,
        progress_percent=round(progress, 1)
    )


def campaign_to_response(campaign_data: dict) -> dict:
    return {
        "id": campaign_data["id"],
        "user_id": campaign_data.get("user_id"),
        "company_id": campaign_data.get("company_id"),
        "name": campaign_data["name"],
        "status": campaign_data.get("status", "draft"),
        "message": {
            "type": campaign_data.get("message_type", "text"),
            "text": campaign_data.get("message_text", ""),
            "media_url": campaign_data.get("media_url"),
            "media_filename": campaign_data.get("media_filename")
        },
        "settings": {
            "interval_min": campaign_data.get("interval_min", 30),
            "interval_max": campaign_data.get("interval_max", 60),
            "start_time": campaign_data.get("start_time"),
            "end_time": campaign_data.get("end_time"),
            "daily_limit": campaign_data.get("daily_limit"),
            "working_days": campaign_data.get("working_days", [0, 1, 2, 3, 4])
        },
        "total_contacts": campaign_data.get("total_contacts", 0),
        "sent_count": campaign_data.get("sent_count", 0),
        "error_count": campaign_data.get("error_count", 0),
        "pending_count": campaign_data.get("pending_count", 0),
        "created_at": campaign_data.get("created_at"),
        "updated_at": campaign_data.get("updated_at"),
        "started_at": campaign_data.get("started_at"),
        "completed_at": campaign_data.get("completed_at")
    }


# ========== Root Endpoint ==========
@api_router.get("/")
async def root():
    return {"message": "Lead Dispatcher API", "version": "2.2.0", "mode": "SaaS Hybrid"}

# ========== NEW: Health Check ==========
@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# ========== WhatsApp Debug Endpoint ==========
@api_router.get("/whatsapp/debug")
async def debug_whatsapp_session(
    request: Request,
    auth_user: dict = Depends(get_authenticated_user)
):
    """Endpoint de diagnóstico para verificar configuração da sessão WAHA"""
    company_id = auth_user.get("company_id")
    user_id = auth_user.get("user_id")
    
    db = get_db()
    
    # Buscar dados da empresa
    company_data = None
    try:
        company_result = db.client.table('companies')\
            .select('id, name')\
            .eq('id', company_id)\
            .single()\
            .execute()
        company_data = company_result.data
    except Exception as e:
        company_data = {"error": str(e)}
    
    # Buscar config da sessão
    waha_config = await db.get_waha_config(company_id)
    
    # Calcular nome da sessão que seria gerado
    session_name = await get_session_name_for_company(company_id)
    
    return {
        "user_id": user_id,
        "company_id": company_id,
        "company_data": company_data,
        "waha_config_from_db": waha_config,
        "computed_session_name": session_name,
        "waha_url": os.getenv('WAHA_DEFAULT_URL'),
    }


# ========== WhatsApp Management ==========

@api_router.get("/whatsapp/status")
async def get_whatsapp_status(
    request: Request,
    auth_user: dict = Depends(get_authenticated_user)
):
    company_id = auth_user.get("company_id")
    if not company_id:
        return {"status": "DISCONNECTED", "connected": False, "error": "Company ID não encontrado"}

    waha_url = os.getenv('WAHA_DEFAULT_URL')
    waha_key = os.getenv('WAHA_MASTER_KEY')
    
    if not waha_url:
        return {"status": "DISCONNECTED", "connected": False, "error": "Server config error"}

    session_name = await get_session_name_for_company(company_id)
    waha = WahaService(waha_url, waha_key, session_name)
    
    conn = await waha.check_connection()
    
    status_map = {
        "STOPPED": "DISCONNECTED",
        "STARTING": "STARTING",
        "SCAN_QR_CODE": "SCANNING",
        "SCANNING": "SCANNING",
        "WORKING": "CONNECTED",
        "CONNECTED": "CONNECTED",
        "FAILED": "DISCONNECTED"
    }
    
    waha_raw_status = conn.get("status", "DISCONNECTED")
    
    return {
        "status": status_map.get(waha_raw_status, "DISCONNECTED"),
        "connected": conn.get("connected", False),
        "session_name": session_name,
        "waha_raw_status": waha_raw_status
    }


@api_router.post("/whatsapp/session/start")
async def start_whatsapp_session(
    request: Request,
    auth_user: dict = Depends(get_authenticated_user)
):
    company_id = auth_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="Company ID não encontrado")
    
    waha_url = os.getenv('WAHA_DEFAULT_URL')
    waha_key = os.getenv('WAHA_MASTER_KEY')
    session_name = await get_session_name_for_company(company_id)
    
    logger.info(f"🚀 Iniciando sessão: {session_name} para empresa: {company_id}")

    waha = WahaService(waha_url, waha_key, session_name)
    
    # Passa a URL do backend para configurar o webhook automaticamente
    backend_webhook_url = os.getenv('BACKEND_WEBHOOK_URL') or os.getenv('CORS_ORIGINS', '').split(',')[0].strip()
    result = await waha.start_session(webhook_url=backend_webhook_url)
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))

    return {"status": "STARTING", "message": "Motor em inicialização...", "session_name": session_name}

@api_router.post("/whatsapp/session/stop")
async def stop_whatsapp_session(
    request: Request,
    auth_user: dict = Depends(get_authenticated_user)
):
    company_id = auth_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="Company ID não encontrado")
    
    waha_url = os.getenv('WAHA_DEFAULT_URL')
    waha_key = os.getenv('WAHA_MASTER_KEY')
    session_name = await get_session_name_for_company(company_id)

    waha = WahaService(waha_url, waha_key, session_name)
    success = await waha.stop_session()
    return {"success": success}

@api_router.post("/whatsapp/session/logout")
async def logout_whatsapp_session(
    request: Request,
    auth_user: dict = Depends(get_authenticated_user)
):
    company_id = auth_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="Company ID não encontrado")
    
    waha_url = os.getenv('WAHA_DEFAULT_URL')
    waha_key = os.getenv('WAHA_MASTER_KEY')
    session_name = await get_session_name_for_company(company_id)

    waha = WahaService(waha_url, waha_key, session_name)
    success = await waha.logout_session()
    return {"success": success}

@api_router.get("/whatsapp/qr")
async def get_whatsapp_qr(
    request: Request,
    auth_user: dict = Depends(get_authenticated_user)
):
    company_id = auth_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="Company ID não encontrado")
    
    waha_url = os.getenv('WAHA_DEFAULT_URL')
    waha_key = os.getenv('WAHA_MASTER_KEY')
    session_name = await get_session_name_for_company(company_id)

    waha = WahaService(waha_url, waha_key, session_name)
    return await waha.get_qr_code()


@api_router.post("/whatsapp/webhook/configure")
async def configure_whatsapp_webhook(
    request: Request,
    auth_user: dict = Depends(get_authenticated_user)
):
    """
    Configura o webhook do WAHA para a sessão da empresa.
    Chamado automaticamente quando o usuário conecta o WhatsApp.
    """
    company_id = auth_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="Company ID não encontrado")
    
    waha_url = os.getenv('WAHA_DEFAULT_URL')
    waha_key = os.getenv('WAHA_MASTER_KEY')
    
    # URL do backend para receber webhooks
    backend_url = os.getenv('BACKEND_WEBHOOK_URL') or os.getenv('CORS_ORIGINS', '').split(',')[0].strip()
    
    if not backend_url:
        raise HTTPException(status_code=500, detail="BACKEND_WEBHOOK_URL não configurado no servidor")
    
    session_name = await get_session_name_for_company(company_id)
    waha = WahaService(waha_url, waha_key, session_name)
    
    result = await waha.update_webhook(backend_url)
    
    if result.get("success"):
        logger.info(f"✅ Webhook configurado para empresa {company_id}: {result.get('webhook_url')}")
        return {"success": True, "webhook_url": result.get("webhook_url"), "session_name": session_name}
    else:
        raise HTTPException(status_code=500, detail=result.get("error", "Erro ao configurar webhook"))




# ========== NEW: Lead Validation Endpoint ==========

class ValidateLeadsRequest(BaseModel):
    lead_ids: List[str]

@api_router.post("/leads/validate")
async def validate_leads_batch(
    request: Request,
    payload: ValidateLeadsRequest,
    auth_user: dict = Depends(get_authenticated_user)
):
    """
    Valida uma lista de leads no WAHA para saber se têm WhatsApp.
    Atualiza o banco de dados automaticamente.
    """
    try:
        db = get_db()
        company_id = auth_user["company_id"]
        
        # 1. Configurar WAHA
        waha_url = os.getenv('WAHA_DEFAULT_URL')
        waha_key = os.getenv('WAHA_MASTER_KEY')
        session_name = await get_session_name_for_company(company_id)
        waha = WahaService(waha_url, waha_key, session_name)
        
        # 2. Verificar conexão
        conn = await waha.check_connection()
        if not conn.get("connected"):
            return {"updated": [], "warning": "WhatsApp desconectado"}

        # 3. Buscar os leads no banco
        leads_response = db.client.table("leads")\
            .select("id, phone, has_whatsapp")\
            .in_("id", payload.lead_ids)\
            .eq("company_id", company_id)\
            .execute()
            
        leads = leads_response.data or []
        updated_leads = []
        
        # 4. Validar cada um
        for lead in leads:
            phone = lead.get("phone")
            
            if phone:
                has_whatsapp = await waha.check_number_exists(phone)
                
                # Atualiza se encontrou WhatsApp
                if has_whatsapp:
                    db.client.table("leads")\
                        .update({"has_whatsapp": True})\
                        .eq("id", lead["id"])\
                        .execute()
                    
                    updated_leads.append({"id": lead["id"], "has_whatsapp": True})
        
        return {"updated": updated_leads}

    except Exception as e:
        logger.error(f"Error validating leads: {e}")
        # Não falha a requisição inteira se o Waha der erro, apenas retorna vazio
        return {"updated": [], "error": str(e)}


# ========== Campaign Endpoints ==========
@api_router.post("/campaigns")
@limiter.limit("50/hour")
async def create_campaign(
    request: Request,
    campaign: CampaignCreate,
    auth_user: dict = Depends(get_authenticated_user)
):
    try:
        logger.info(f"📝 Criando campanha: {campaign.name}")
        logger.info(f"📝 Message type: {campaign.message.type}")
        logger.info(f"📝 Settings: interval={campaign.settings.interval_min}-{campaign.settings.interval_max}")
        
        db = get_db()
        await validate_quota_for_action(
            user_id=auth_user["user_id"],
            action="create_campaign",
            required_plan=["intermediario", "avancado"],
            db=db
        )
        
        campaign_data = {
            "id": str(uuid.uuid4()),
            "company_id": auth_user["company_id"],
            "user_id": auth_user["user_id"],
            "name": campaign.name,
            "status": "draft",
            "message_type": campaign.message.type,
            "message_text": campaign.message.text,
            "media_url": campaign.message.media_url,
            "media_filename": campaign.message.media_filename,
            "interval_min": campaign.settings.interval_min,
            "interval_max": campaign.settings.interval_max,
            "start_time": campaign.settings.start_time,
            "end_time": campaign.settings.end_time,
            "daily_limit": campaign.settings.daily_limit,
            "working_days": campaign.settings.working_days,
            "total_contacts": 0,
            "sent_count": 0,
            "error_count": 0,
            "pending_count": 0
        }
        
        # Tentar adicionar timezone se a coluna existir (graceful degradation)
        # O timezone será buscado da empresa se não estiver na campanha
        
        result = await db.create_campaign(campaign_data)
        if not result:
            raise HTTPException(status_code=500, detail="Erro ao criar campanha")
        
        await db.increment_quota(auth_user["user_id"], "create_campaign")
        
        return campaign_to_response(result)
    
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao criar campanha")


class CampaignFromLeadsRequest(BaseModel):
    """Request para criar campanha diretamente dos leads buscados"""
    name: str
    message: CampaignMessage
    settings: CampaignSettings = Field(default_factory=CampaignSettings)
    contacts: List[dict]  # Lista de {name, phone, category?, extra_data?}


@api_router.post("/campaigns/from-leads")
@limiter.limit("20/hour")
async def create_campaign_from_leads(
    request: Request,
    data: CampaignFromLeadsRequest,
    auth_user: dict = Depends(get_authenticated_user)
):
    """
    Cria uma campanha e adiciona contatos diretamente (sem precisar de arquivo).
    Usado para criar campanhas diretamente da página de busca de leads.
    """
    try:
        logger.info(f"📝 Criando campanha dos leads: {data.name} ({len(data.contacts)} contatos)")
        
        db = get_db()
        await validate_quota_for_action(
            user_id=auth_user["user_id"],
            action="create_campaign",
            required_plan=["intermediario", "avancado"],
            db=db
        )
        
        # Validar contatos
        if not data.contacts or len(data.contacts) == 0:
            raise HTTPException(status_code=400, detail="É necessário pelo menos 1 contato")
        
        # Limitar a 5000 contatos por vez para não sobrecarregar
        if len(data.contacts) > 5000:
            raise HTTPException(status_code=400, detail="Máximo de 5000 contatos por campanha")
        
        campaign_id = str(uuid.uuid4())
        
        # 1. Criar campanha
        campaign_data = {
            "id": campaign_id,
            "company_id": auth_user["company_id"],
            "user_id": auth_user["user_id"],
            "name": data.name,
            "status": "draft",
            "message_type": data.message.type,
            "message_text": data.message.text,
            "media_url": data.message.media_url,
            "media_filename": data.message.media_filename,
            "interval_min": data.settings.interval_min,
            "interval_max": data.settings.interval_max,
            "start_time": data.settings.start_time,
            "end_time": data.settings.end_time,
            "daily_limit": data.settings.daily_limit,
            "working_days": data.settings.working_days,
            "total_contacts": len(data.contacts),
            "sent_count": 0,
            "error_count": 0,
            "pending_count": len(data.contacts)
        }
        
        # Nota: timezone será buscado da empresa se não estiver na campanha
        
        result = await db.create_campaign(campaign_data)
        if not result:
            raise HTTPException(status_code=500, detail="Erro ao criar campanha")
        
        # 2. Inserir contatos em batch (eficiente para Supabase)
        contacts_to_insert = []
        for contact in data.contacts:
            phone = contact.get("phone", "").strip()
            # Limpar telefone
            phone = ''.join(filter(str.isdigit, phone))
            if len(phone) < 10:
                continue  # Pular telefones inválidos
            
            contacts_to_insert.append({
                "campaign_id": campaign_id,
                "name": contact.get("name", "Sem nome")[:100],
                "phone": phone,
                "category": contact.get("category", "")[:50] if contact.get("category") else None,
                "extra_data": contact.get("extra_data", {}),
                "status": "pending"
            })
        
        # Inserir em batches de 500 para não sobrecarregar
        batch_size = 500
        for i in range(0, len(contacts_to_insert), batch_size):
            batch = contacts_to_insert[i:i + batch_size]
            db.client.table("campaign_contacts").insert(batch).execute()
        
        # 3. Atualizar contagem real (pode ter removido inválidos)
        actual_count = len(contacts_to_insert)
        if actual_count != len(data.contacts):
            db.client.table("campaigns").update({
                "total_contacts": actual_count,
                "pending_count": actual_count
            }).eq("id", campaign_id).execute()
        
        # 4. Incrementar quota
        await db.increment_quota(auth_user["user_id"], "create_campaign")
        
        logger.info(f"✅ Campanha {campaign_id} criada com {actual_count} contatos")
        
        # Retornar campanha criada
        final_result = db.client.table("campaigns").select("*").eq("id", campaign_id).single().execute()
        return campaign_to_response(final_result.data) if final_result.data else result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar campanha dos leads: {e}")
        raise handle_error(e, "Erro ao criar campanha")


@api_router.get("/campaigns")
async def list_campaigns(
    request: Request,
    auth_user: dict = Depends(get_authenticated_user),
    limit: int = 50,
    skip: int = 0
):
    try:
        db = get_db()
        company_id = auth_user["company_id"]
        campaigns_data = await db.get_campaigns_by_company(company_id, limit, skip)
        
        campaigns_with_stats = []
        for c in campaigns_data:
            campaign_dict = campaign_to_response(c)
            campaign_dict["stats"] = calculate_campaign_stats(c).dict()
            campaign_dict["is_worker_running"] = is_campaign_running(c["id"])
            campaigns_with_stats.append(campaign_dict)
        
        return {"campaigns": campaigns_with_stats}
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao listar campanhas")


@api_router.get("/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    auth_user: dict = Depends(get_authenticated_user)
):
    try:
        db = get_db()
        campaign_data = await validate_campaign_ownership(
            campaign_id, 
            auth_user["company_id"],
            db
        )
        stats = calculate_campaign_stats(campaign_data)
        return {
            "campaign": campaign_to_response(campaign_data),
            "stats": stats,
            "is_worker_running": is_campaign_running(campaign_id)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao buscar campanha")


@api_router.put("/campaigns/{campaign_id}")
async def update_campaign(
    campaign_id: str,
    update: CampaignUpdate,
    auth_user: dict = Depends(get_authenticated_user)
):
    try:
        db = get_db()
        campaign_data = await validate_campaign_ownership(
            campaign_id,
            auth_user["company_id"],
            db
        )
        
        update_dict = {}
        if update.name is not None:
            update_dict["name"] = update.name
        if update.message is not None:
            update_dict["message_type"] = update.message.type.value
            update_dict["message_text"] = update.message.text
            update_dict["media_url"] = update.message.media_url
            update_dict["media_filename"] = update.message.media_filename
        if update.settings is not None:
            update_dict["interval_min"] = update.settings.interval_min
            update_dict["interval_max"] = update.settings.interval_max
            update_dict["start_time"] = update.settings.start_time
            update_dict["end_time"] = update.settings.end_time
            update_dict["daily_limit"] = update.settings.daily_limit
            update_dict["working_days"] = update.settings.working_days
        
        if update_dict:
            updated = await db.update_campaign(campaign_id, update_dict)
            if updated:
                return campaign_to_response(updated)
        
        return campaign_to_response(campaign_data)
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao atualizar campanha")


@api_router.delete("/campaigns/{campaign_id}")
async def delete_campaign(
    campaign_id: str,
    auth_user: dict = Depends(get_authenticated_user)
):
    try:
        db = get_db()
        await validate_campaign_ownership(
            campaign_id,
            auth_user["company_id"],
            db
        )
        await stop_campaign_worker(campaign_id)
        await db.delete_contacts_by_campaign(campaign_id)
        await db.delete_message_logs_by_campaign(campaign_id)
        result = await db.delete_campaign(campaign_id)
        if not result:
            raise HTTPException(status_code=404, detail="Campanha não encontrada")
        return {"success": True, "message": "Campanha excluída com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao deletar campanha")


@api_router.post("/campaigns/{campaign_id}/upload")
@limiter.limit("10/hour")
async def upload_contacts(
    request: Request,
    campaign_id: str,
    file: UploadFile = File(...),
    phone_column: str = Form(default="Telefone"),
    name_column: str = Form(default="Nome"),
    auth_user: dict = Depends(get_authenticated_user)
):
    try:
        logger.info(f"📤 Upload iniciado para campanha: {campaign_id}")
        logger.info(f"📤 Arquivo: {file.filename if file else 'NONE'}")
        logger.info(f"📤 Colunas: phone={phone_column}, name={name_column}")
        
        db = get_db()
        campaign_data = await validate_campaign_ownership(
            campaign_id,
            auth_user["company_id"],
            db
        )
        
        content = await file.read()
        logger.info(f"📤 Arquivo lido: {len(content)} bytes")
        
        is_valid, error_msg = validate_file_upload(content, file.filename)
        logger.info(f"📤 Validação: is_valid={is_valid}, error={error_msg}")
        
        if not is_valid:
            logger.error(f"📤 Validação falhou: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
        
        try:
            logger.info(f"📤 Processando arquivo Excel/CSV...")
            if file.filename.endswith('.xlsx') or file.filename.endswith('.xls'):
                df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
            else:
                try:
                    df = pd.read_excel(io.BytesIO(content), encoding='utf-8')
                except UnicodeDecodeError:
                    df = pd.read_csv(io.BytesIO(content), encoding='latin-1')
            logger.info(f"📤 Arquivo lido com sucesso. {len(df)} linhas, {len(df.columns)} colunas")
        except Exception as e:
            logger.error(f"📤 Erro ao ler arquivo: {e}")
            raise HTTPException(status_code=400, detail=f"Erro ao ler arquivo: formato inválido")
        
        df.columns = df.columns.str.strip()
        phone_col = None
        name_col = None
        
        for col in df.columns:
            col_lower = col.lower()
            if phone_column.lower() in col_lower or col_lower in ['telefone', 'phone', 'tel', 'celular', 'whatsapp']:
                phone_col = col
            if name_column.lower() in col_lower or col_lower in ['nome', 'name', 'empresa', 'company']:
                name_col = col
        
        if not phone_col:
            raise HTTPException(
                status_code=400, 
                detail=f"Coluna de telefone não encontrada. Colunas disponíveis: {list(df.columns)}"
            )
        
        await db.delete_contacts_by_campaign(campaign_id)
        
        contacts = []
        skipped = 0
        
        for _, row in df.iterrows():
            phone = str(row[phone_col]).strip() if pd.notna(row[phone_col]) else ""
            if not phone or phone == "nan":
                skipped += 1
                continue
            
            raw_name = str(row[name_col]).strip() if name_col and pd.notna(row.get(name_col)) else "Sem nome"
            name = sanitize_csv_value(raw_name)
            
            extra_data = {}
            for col in df.columns:
                if col not in [phone_col, name_col]:
                    value = row[col]
                    if pd.notna(value):
                        extra_data[col] = sanitize_csv_value(value)
            
            contact = {
                "id": str(uuid.uuid4()),
                "campaign_id": campaign_id,
                "name": name,
                "phone": phone,
                "email": extra_data.get("Email") or extra_data.get("email"),
                "category": extra_data.get("Categoria") or extra_data.get("categoria") or extra_data.get("Category"),
                "extra_data": extra_data,
                "status": "pending"
            }
            contacts.append(contact)
        
        if contacts:
            await db.create_contacts(contacts)
        
        await db.update_campaign(campaign_id, {
            "total_contacts": len(contacts),
            "pending_count": len(contacts),
            "sent_count": 0,
            "error_count": 0,
            "status": "ready"
        })
        
        return {
            "success": True,
            "total_imported": len(contacts),
            "skipped": skipped,
            "columns_found": list(df.columns),
            "phone_column_used": phone_col,
            "name_column_used": name_col
        }
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao processar arquivo de contatos")


@api_router.get("/campaigns/{campaign_id}/contacts")
async def get_campaign_contacts(
    campaign_id: str,
    auth_user: dict = Depends(get_authenticated_user),
    status: Optional[str] = None,
    limit: int = 100,
    skip: int = 0
):
    try:
        db = get_db()
        await validate_campaign_ownership(
            campaign_id,
            auth_user["company_id"],
            db
        )
        contacts_data = await db.get_contacts_by_campaign(campaign_id, status, limit, skip)
        total = await db.count_contacts(campaign_id, status)
        return {"contacts": contacts_data, "total": total, "limit": limit, "skip": skip}
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao buscar contatos")


@api_router.post("/campaigns/{campaign_id}/start")
@limiter.limit("30/hour")
async def start_campaign(
    request: Request,
    campaign_id: str, 
    background_tasks: BackgroundTasks,
    auth_user: dict = Depends(get_authenticated_user),
    waha_url: Optional[str] = None,
    waha_api_key: Optional[str] = None,
    waha_session: Optional[str] = "default"
):
    try:
        db = get_db()
        campaign_data = await validate_campaign_ownership(
            campaign_id,
            auth_user["company_id"],
            db
        )
        await validate_quota_for_action(
            user_id=auth_user["user_id"],
            action="start_campaign",
            required_plan=["intermediario", "avancado"],
            db=db
        )
        
        if campaign_data.get("total_contacts", 0) == 0:
            raise HTTPException(status_code=400, detail="Campanha não tem contatos. Faça upload primeiro.")
        
        final_waha_url = os.getenv('WAHA_DEFAULT_URL') or waha_url
        final_waha_key = os.getenv('WAHA_MASTER_KEY') or waha_api_key
        
        if not final_waha_url or not final_waha_key:
            raise HTTPException(
                status_code=500, 
                detail="Erro de configuração: WAHA_DEFAULT_URL não configurada no servidor."
            )
        
        target_company_id = auth_user["company_id"]
        if waha_session and waha_session != "default":
            final_session = waha_session
        else:
            final_session = await get_session_name_for_company(target_company_id)

        waha = WahaService(final_waha_url, final_waha_key, final_session)
        connection = await waha.check_connection()
        if not connection.get("connected"):
            raise HTTPException(
                status_code=400, 
                detail="WhatsApp desconectado. Vá em Configurações e clique em 'Gerar QR Code'."
            )
        
        await db.update_campaign(campaign_id, {
            "status": "running",
            "started_at": datetime.utcnow().isoformat()
        })
        
        success, error = await start_campaign_worker(db, campaign_id, waha)
        if not success:
            await db.update_campaign(campaign_id, {"status": "ready"})
            raise HTTPException(status_code=400, detail=error or "Campanha já em execução")
        
        await db.increment_quota(auth_user["user_id"], "start_campaign")
        return {"success": True, "message": "Campanha iniciada com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao iniciar campanha")


@api_router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: str,
    auth_user: dict = Depends(get_authenticated_user)
):
    try:
        db = get_db()
        await validate_campaign_ownership(
            campaign_id,
            auth_user["company_id"],
            db
        )
        await stop_campaign_worker(campaign_id)
        await db.update_campaign(campaign_id, {"status": "paused"})
        return {"success": True, "message": "Campanha pausada"}
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao pausar campanha")


@api_router.post("/campaigns/{campaign_id}/cancel")
async def cancel_campaign(
    campaign_id: str,
    auth_user: dict = Depends(get_authenticated_user)
):
    try:
        db = get_db()
        await validate_campaign_ownership(
            campaign_id,
            auth_user["company_id"],
            db
        )
        await stop_campaign_worker(campaign_id)
        await db.update_campaign(campaign_id, {"status": "cancelled"})
        return {"success": True, "message": "Campanha cancelada"}
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao cancelar campanha")


@api_router.post("/campaigns/{campaign_id}/reset")
async def reset_campaign(
    campaign_id: str,
    auth_user: dict = Depends(get_authenticated_user)
):
    try:
        db = get_db()
        await validate_campaign_ownership(
            campaign_id,
            auth_user["company_id"],
            db
        )
        await stop_campaign_worker(campaign_id)
        await db.reset_contacts_status(campaign_id)
        total = await db.count_contacts(campaign_id)
        await db.update_campaign(campaign_id, {
            "status": "ready",
            "total_contacts": total,
            "pending_count": total,
            "sent_count": 0,
            "error_count": 0,
            "started_at": None,
            "completed_at": None
        })
        await db.delete_message_logs_by_campaign(campaign_id)
        return {"success": True, "message": "Campanha resetada"}
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao resetar campanha")


@api_router.get("/campaigns/{campaign_id}/logs")
async def get_message_logs(
    campaign_id: str,
    auth_user: dict = Depends(get_authenticated_user),
    status: Optional[str] = None,
    limit: int = 100,
    skip: int = 0
):
    try:
        db = get_db()
        await validate_campaign_ownership(
            campaign_id,
            auth_user["company_id"],
            db
        )
        logs_data = await db.get_message_logs(campaign_id, status, limit, skip)
        total = await db.count_message_logs(campaign_id, status)
        return {"logs": logs_data, "total": total, "limit": limit, "skip": skip}
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao buscar logs de mensagens")


@api_router.get("/dashboard/stats")
async def get_dashboard_stats(auth_user: dict = Depends(get_authenticated_user)):
    try:
        db = get_db()
        stats = await db.get_dashboard_stats(auth_user["company_id"])
        return stats
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao buscar estatísticas")


@api_router.get("/notifications")
async def get_notifications(
    auth_user: dict = Depends(get_authenticated_user),
    limit: int = 50,
    unread_only: bool = False
):
    try:
        db = get_db()
        notifications = await db.get_notifications(auth_user["user_id"], limit, unread_only)
        return {"notifications": notifications}
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao buscar notificações")


@api_router.get("/notifications/unread-count")
async def get_unread_count(auth_user: dict = Depends(get_authenticated_user)):
    try:
        db = get_db()
        count = await db.get_unread_notification_count(auth_user["user_id"])
        return {"unread_count": count}
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao buscar contagem de notificações")


@api_router.put("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    auth_user: dict = Depends(get_authenticated_user)
):
    try:
        db = get_db()
        success = await db.mark_notification_read(notification_id)
        if not success:
            raise HTTPException(status_code=404, detail="Notificação não encontrada")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao marcar notificação como lida")


@api_router.put("/notifications/mark-all-read")
async def mark_all_read(auth_user: dict = Depends(get_authenticated_user)):
    try:
        db = get_db()
        success = await db.mark_all_notifications_read(auth_user["user_id"])
        return {"success": success}
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao marcar todas as notificações como lidas")


@api_router.get("/quotas/me")
async def get_my_quota(auth_user: dict = Depends(get_authenticated_user)):
    try:
        db = get_db()
        quota = await db.get_user_quota(auth_user["user_id"])
        if not quota:
            raise HTTPException(status_code=404, detail="Quota não encontrada")
        return quota
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao buscar quota")


@api_router.post("/quotas/check")
async def check_quota_endpoint(
    action: str,
    auth_user: dict = Depends(get_authenticated_user)
):
    try:
        db = get_db()
        result = await db.check_quota(auth_user["user_id"], action)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao verificar quota")


@api_router.post("/quotas/increment")
async def increment_quota_endpoint(
    action: str,
    amount: int = 1,
    auth_user: dict = Depends(get_authenticated_user)
):
    try:
        db = get_db()
        success = await db.increment_quota(auth_user["user_id"], action, amount)
        return {"success": success}
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao incrementar quota")


# ========== WAHA Webhook (recebe mensagens do WhatsApp) ==========
@api_router.post("/webhook/waha")
async def waha_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Recebe webhooks do WAHA (mensagens do WhatsApp).
    Fluxo: WAHA → Backend → n8n → OpenAI → WAHA (resposta)
    """
    try:
        payload = await request.json()
        event = payload.get("event")
        
        # Só processa mensagens recebidas
        if event == "message":
            background_tasks.add_task(process_waha_message_for_n8n, payload)
            return {"status": "processing"}
        
        return {"status": "ignored", "event": event}
    except Exception as e:
        logger.error(f"❌ Erro no webhook WAHA: {e}")
        return {"status": "error", "message": str(e)}


# ========== Agent Config Endpoints ==========
class AgentConfigRequest(BaseModel):
    enabled: bool = False
    name: str = "Assistente Virtual"
    personality: Optional[str] = ""
    system_prompt: Optional[str] = ""
    welcome_message: Optional[str] = ""
    response_delay: int = 3
    max_response_length: int = 500
    tone: str = "professional"
    language: str = "pt-BR"
    auto_qualify: bool = True
    qualification_questions: list = []
    blocked_topics: list = []
    working_hours: dict = {
        "enabled": False,
        "start": "09:00",
        "end": "18:00",
        "timezone": "America/Sao_Paulo"
    }


@api_router.get("/agent/config")
async def get_agent_config(auth_user: dict = Depends(get_authenticated_user)):
    """Busca configuração do agente IA da empresa"""
    try:
        db = get_db()
        company_id = auth_user["company_id"]
        
        config = await db.get_agent_config(company_id)
        if not config:
            return {"config": None}
        
        return {"config": config}
    except Exception as e:
        raise handle_error(e, "Erro ao buscar configuração do agente")


@api_router.put("/agent/config")
async def update_agent_config(
    data: AgentConfigRequest,
    auth_user: dict = Depends(get_authenticated_user)
):
    """Salva/atualiza configuração do agente IA da empresa"""
    try:
        db = get_db()
        company_id = auth_user["company_id"]
        
        # Verificar permissão do plano
        await validate_quota_for_action(
            user_id=auth_user["user_id"],
            action="use_agent",
            required_plan=["avancado"],
            db=db
        )
        
        config_data = {
            "enabled": data.enabled,
            "name": data.name,
            "personality": data.personality,
            "system_prompt": data.system_prompt,
            "welcome_message": data.welcome_message,
            "response_delay": data.response_delay,
            "max_response_length": data.max_response_length,
            "tone": data.tone,
            "language": data.language,
            "auto_qualify": data.auto_qualify,
            "qualification_questions": data.qualification_questions,
            "blocked_topics": data.blocked_topics,
            "working_hours": data.working_hours,
        }
        
        result = await db.upsert_agent_config(company_id, config_data)
        if not result:
            raise HTTPException(status_code=500, detail="Erro ao salvar configuração")
        
        logger.info(f"🤖 Config do agente atualizada para empresa {company_id}")
        return {"config": result, "success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise handle_error(e, "Erro ao salvar configuração do agente")


# Include the router in the main app
app.include_router(api_router)
app.include_router(webhook_router)
app.include_router(admin_router)
app.include_router(security_router)

cors_origins_str = os.environ.get('CORS_ORIGINS', '')
if cors_origins_str and cors_origins_str != '*':
    cors_origins = [origin.strip() for origin in cors_origins_str.split(',') if origin.strip()]
else:
    cors_origins = ["http://localhost:3000", "http://localhost:5173"]
    logger.warning("⚠️ CORS_ORIGINS não configurado - usando apenas localhost")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "Accept", "X-Session-Token"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response