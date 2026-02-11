import os
import httpx
import logging
from supabase_service import get_supabase_service

logger = logging.getLogger(__name__)

async def process_waha_message_for_n8n(payload: dict):
    """
    Processa webhook do WAHA, valida se a empresa tem o agente ativo
    e encaminha para o n8n gerar a resposta.
    """
    try:
        # 1. Obter URL do Webhook do ambiente
        n8n_url = os.getenv("N8N_WEBHOOK_URL")
        if not n8n_url:
            logger.error("❌ N8N_WEBHOOK_URL não configurada no .env")
            return

        # 2. Extrair dados básicos
        event = payload.get("event")
        if event != "message": return
        
        msg_payload = payload.get("payload", {})
        
        # Ignorar mensagens enviadas por mim ou grupos
        # O filtro @g.us remove grupos
        if msg_payload.get("fromMe") or "@g.us" in msg_payload.get("from", ""):
            return
        
        session_name = payload.get("session")
        sender = msg_payload.get("from")
        body = msg_payload.get("body")
        
        if not body or not sender: return

        db = get_supabase_service()

        # 3. Identificar a Empresa pela Sessão
        company_id = None
        
        # Tenta buscar pelo company_settings (padrão novo)
        settings_res = db.client.table("company_settings")\
            .select("company_id")\
            .eq("waha_session", session_name)\
            .maybe_single().execute()
            
        if settings_res.data:
            company_id = settings_res.data["company_id"]
        
        # Fallback para waha_configs (legado)
        if not company_id:
            waha_res = db.client.table("waha_configs")\
                .select("company_id")\
                .eq("session_name", session_name)\
                .maybe_single().execute()
            if waha_res.data:
                company_id = waha_res.data["company_id"]

        if not company_id:
            #logger.warning(f"⚠️ Agente: Empresa não encontrada para sessão {session_name}")
            return 

        # 4. Buscar Configuração do Agente
        agent_config = await db.get_agent_config(company_id)
        
        # Verifica se está habilitado
        if not agent_config or not agent_config.get("enabled"):
            return 

        # 5. Enviar payload para o n8n
        n8n_payload = {
            "message": body,
            "sender": sender,
            "session_name": session_name,
            "company_id": company_id,
            "contact_name": msg_payload.get("_data", {}).get("notifyName", "Cliente"),
            "agent_config": {
                "name": agent_config.get("name", "Assistente"),
                "personality": agent_config.get("personality", ""),
                "system_prompt": agent_config.get("system_prompt", ""),
                "response_delay": agent_config.get("response_delay", 3),
                "full_config": agent_config 
            }
        }

        # Disparo assíncrono (Fire & Forget)
        async with httpx.AsyncClient() as client:
            try:
                await client.post(n8n_url, json=n8n_payload, timeout=5.0)
                logger.info(f"🤖 Agente IA acionado para: {sender} (via n8n)")
            except Exception as e:
                logger.error(f"❌ Erro ao chamar n8n: {e}")

    except Exception as e:
        logger.error(f"❌ Erro no processamento do agente: {e}")
