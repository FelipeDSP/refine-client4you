import os
import httpx
import logging
from supabase_service import get_supabase_service

logger = logging.getLogger(__name__)

async def process_waha_message_for_n8n(payload: dict):
    """
    Processa webhook do WAHA, valida se a empresa tem o agente ativo
    e encaminha para o n8n gerar a resposta.
    
    O payload é enviado no formato compatível com WAHA Trigger do n8n,
    facilitando a adaptação de workflows existentes.
    """
    try:
        # 1. Obter URL do Webhook do ambiente
        n8n_url = os.getenv("N8N_WEBHOOK_URL")
        if not n8n_url:
            logger.warning("⚠️ N8N_WEBHOOK_URL não configurada - Agente IA desabilitado")
            return

        # 2. Extrair dados básicos
        event = payload.get("event")
        if event != "message": 
            return
        
        msg_payload = payload.get("payload", {})
        
        # Ignorar mensagens enviadas por mim ou grupos
        if msg_payload.get("fromMe") or "@g.us" in msg_payload.get("from", ""):
            return
        
        session_name = payload.get("session")
        sender = msg_payload.get("from")
        body = msg_payload.get("body")
        
        if not body or not sender: 
            return

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
            return 

        # 4. Buscar Configuração do Agente
        agent_config = await db.get_agent_config(company_id)
        
        # Log de debug
        logger.info(f"🔍 Agent config para {company_id}: enabled={agent_config.get('enabled') if agent_config else 'None'}, openai_key={'Sim' if agent_config and agent_config.get('openai_api_key') else 'Não'}")
        
        # Verifica se está habilitado
        if not agent_config or not agent_config.get("enabled"):
            return 

        # 5. Buscar dados da empresa e WAHA config
        company_res = db.client.table("companies")\
            .select("name")\
            .eq("id", company_id)\
            .maybe_single().execute()
        company_name = company_res.data.get("name", "") if company_res.data else ""
        
        # Buscar configurações do WAHA (URL e API Key)
        waha_url = os.getenv("WAHA_DEFAULT_URL", "")
        waha_api_key = os.getenv("WAHA_MASTER_KEY", "")
        
        # Tentar buscar config específica da empresa
        company_waha_res = db.client.table("company_settings")\
            .select("waha_api_url, waha_api_key")\
            .eq("company_id", company_id)\
            .maybe_single().execute()
        
        if company_waha_res.data:
            if company_waha_res.data.get("waha_api_url"):
                waha_url = company_waha_res.data["waha_api_url"]
            if company_waha_res.data.get("waha_api_key"):
                waha_api_key = company_waha_res.data["waha_api_key"]

        # 6. Extrair telefone normalizado
        telefone_normalizado = sender.replace("@c.us", "").replace("@s.whatsapp.net", "")
        
        # 7. Montar payload compatível com WAHA Trigger do n8n
        # Este formato permite reutilizar workflows existentes com mínimas alterações
        n8n_payload = {
            # === Dados no formato WAHA Trigger ===
            "payload": msg_payload,  # Payload original do WAHA
            
            # === Dados extraídos e normalizados ===
            "telefone_normalizado": telefone_normalizado,
            "texto_cliente": body,
            
            # === Variáveis para o workflow ===
            "variaveis": {
                "server_url": waha_url,
                "instancia": session_name,
                "api_key": waha_api_key,
                "phone": telefone_normalizado,
                "mensagem": body,
            },
            
            # === Credenciais OpenAI do cliente ===
            "openai": {
                "api_key": agent_config.get("openai_api_key", ""),
                "model": agent_config.get("model", "gpt-4.1-mini"),
                "temperature": float(agent_config.get("temperature", 0.7)),
            },
            
            # === Contexto da empresa (Client4You) ===
            "client4you": {
                "company_id": company_id,
                "company_name": company_name,
                "session_name": session_name,
                "agent_config": {
                    "name": agent_config.get("name", "Assistente"),
                    "personality": agent_config.get("personality", ""),
                    "system_prompt": agent_config.get("system_prompt", ""),
                    "response_delay": agent_config.get("response_delay", 3),
                    "model": agent_config.get("model", "gpt-4.1-mini"),
                    "temperature": float(agent_config.get("temperature", 0.7)),
                }
            },
            
            # === Metadados ===
            "event": "message",
            "session": session_name,
            "sender": sender,
            "contact_name": msg_payload.get("_data", {}).get("notifyName", "Cliente"),
            "timestamp": msg_payload.get("timestamp"),
            
            # === Tipo de mensagem ===
            "message_type": "audio" if msg_payload.get("hasMedia") and msg_payload.get("type") == "ptt" else "text",
            "has_media": msg_payload.get("hasMedia", False),
            "media_url": msg_payload.get("media", {}).get("url") if msg_payload.get("hasMedia") else None,
        }

        # Log do payload para debug (sem expor a API key completa)
        openai_key = agent_config.get("openai_api_key", "")
        logger.info(f"📤 Payload OpenAI: model={agent_config.get('model')}, temp={agent_config.get('temperature')}, has_key={'Sim' if openai_key else 'Não'}")

        # Disparo assíncrono (Fire & Forget)
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(n8n_url, json=n8n_payload, timeout=10.0)
                if response.status_code in [200, 201, 204]:
                    logger.info(f"🤖 Agente IA acionado para: {sender} (n8n)")
                else:
                    logger.warning(f"⚠️ n8n retornou status {response.status_code}")
            except httpx.TimeoutException:
                logger.warning(f"⚠️ Timeout ao chamar n8n para {sender}")
            except Exception as e:
                logger.error(f"❌ Erro ao chamar n8n: {e}")

    except Exception as e:
        logger.error(f"❌ Erro no processamento do agente: {e}")


async def get_agent_status(company_id: str) -> dict:
    """
    Retorna o status atual do agente IA para uma empresa.
    """
    try:
        db = get_supabase_service()
        config = await db.get_agent_config(company_id)
        
        n8n_configured = bool(os.getenv("N8N_WEBHOOK_URL"))
        
        return {
            "enabled": config.get("enabled", False) if config else False,
            "n8n_configured": n8n_configured,
            "config": config,
            "status": "active" if (config and config.get("enabled") and n8n_configured) else "inactive"
        }
    except Exception as e:
        logger.error(f"Erro ao buscar status do agente: {e}")
        return {"enabled": False, "n8n_configured": False, "status": "error"}
