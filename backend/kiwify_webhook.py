"""
Kiwify Webhook Handler
Processa eventos de pagamento, cancelamento e reembolso
Agora com criação automática de contas!
"""
from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
import hmac
import hashlib
import logging
import secrets
import string
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

from supabase_service import SupabaseService
from email_service import get_email_service

logger = logging.getLogger(__name__)

# Usar prefixo /api para garantir roteamento correto no Kubernetes
webhook_router = APIRouter(prefix="/api")

# Configuração Kiwify
KIWIFY_WEBHOOK_SECRET = os.environ.get('KIWIFY_WEBHOOK_SECRET', '')

# Mapeamento por nome do plano (como aparece no Kiwify)
PLAN_NAME_MAP = {
    'básico': 'basico',
    'basico': 'basico',
    'intermediário': 'intermediario',
    'intermediario': 'intermediario',
    'avançado': 'avancado',
    'avancado': 'avancado',
}

# Configurações de limites por plano (SEM DEMO - apenas planos pagos)
PLAN_LIMITS = {
    'basico': {
        'name': 'Plano Básico',
        'leads_limit': -1,  # Ilimitado
        'campaigns_limit': 0,  # Sem disparador
        'messages_limit': 0,
        'expires_days': None  # Não expira (enquanto pago)
    },
    'intermediario': {
        'name': 'Plano Intermediário',
        'leads_limit': -1,
        'campaigns_limit': -1,  # Ilimitado
        'messages_limit': -1,
        'expires_days': None
    },
    'avancado': {
        'name': 'Plano Avançado',
        'leads_limit': -1,
        'campaigns_limit': -1,
        'messages_limit': -1,
        'whatsapp_instances': 5,  # Múltiplas instâncias
        'expires_days': None
    }
}

class KiwifyWebhookPayload(BaseModel):
    """Estrutura do webhook Kiwify"""
    event_type: str  # 'order.paid', 'order.refunded', 'subscription.canceled'
    order_id: str
    order_status: str
    product_id: str
    product_name: str
    customer_email: str
    customer_name: str
    customer_phone: Optional[str] = None
    amount: float
    commission_amount: Optional[float] = None
    refunded_at: Optional[str] = None
    canceled_at: Optional[str] = None
    subscription_id: Optional[str] = None
    subscription_status: Optional[str] = None
    created_at: str


def verify_kiwify_signature(payload: bytes, signature: str) -> bool:
    """Verifica assinatura do webhook Kiwify"""
    if not KIWIFY_WEBHOOK_SECRET:
        logger.error("KIWIFY_WEBHOOK_SECRET não configurado - rejeitando webhook")
        return False
    
    if not signature:
        logger.warning("Assinatura não fornecida no webhook")
        return False
    
    expected_signature = hmac.new(
        KIWIFY_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


def generate_temporary_password(length=12):
    """Gera uma senha segura e amigável"""
    alphabet = string.ascii_letters + string.digits + "!@#$%&"
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password


async def get_user_by_email(email: str) -> Optional[Dict]:
    """Busca usuário pelo email"""
    try:
        db = SupabaseService()
        result = db.client.table('profiles').select('*').eq('email', email).maybe_single().execute()
        return result.data
    except Exception as e:
        logger.error(f"Erro ao buscar usuário por email: {e}")
        return None


async def create_new_user(email: str, name: str) -> Dict:
    """
    Cria um novo usuário no Supabase Auth e retorna os dados
    """
    try:
        db = SupabaseService()
        password = generate_temporary_password()
        
        logger.info(f"🆕 Criando novo usuário para: {email}")
        
        # Cria usuário no Auth (Admin API)
        # O SupabaseService usa a chave service_role, então tem permissão de admin
        user_attributes = {
            "email": email,
            "password": password,
            "email_confirm": True, # Já confirma o email pois pagou
            "user_metadata": {"full_name": name}
        }
        
        # A chamada exata depende da versão do cliente, mas geralmente é admin.create_user
        auth_response = db.client.auth.admin.create_user(user_attributes)
        
        # O objeto retornado tem user dentro
        new_user = auth_response.user
        
        # Pequeno delay para garantir que triggers de banco (se houver) rodem
        await asyncio.sleep(1)
        
        return {
            "id": new_user.id,
            "email": email,
            "password": password, # Retornamos a senha para enviar por email
            "is_new": True
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar novo usuário: {e}")
        raise e


async def upgrade_user_to_plan(user_id: str, plan: str, subscription_id: str, order_id: str):
    """
    Upgrade do plano do usuário (Usando UPSERT para garantir criação)
    """
    try:
        db = SupabaseService()
        
        # Calcular data de expiração (30 dias para planos pagos)
        valid_until = (datetime.now() + timedelta(days=30)).isoformat()
        
        # Buscar configuração do plano
        plan_key = plan.lower()
        plan_config = PLAN_LIMITS.get(plan_key, PLAN_LIMITS['demo'])
        
        # Dados para atualização/inserção
        quota_data = {
            'user_id': user_id,
            'plan_type': plan_key,
            'plan_name': plan_config['name'],
            'leads_limit': plan_config['leads_limit'],
            'campaigns_limit': plan_config['campaigns_limit'],
            'messages_limit': plan_config['messages_limit'],
            'plan_expires_at': valid_until,
            'subscription_id': subscription_id,
            'order_id': order_id,
            'updated_at': datetime.now().isoformat()
        }
        
        # UPSERT: Atualiza se existir, Cria se não existir
        db.client.table('user_quotas').upsert(quota_data, on_conflict='user_id').execute()
        
        logger.info(f"✅ Usuário {user_id} atualizado/criado com plano {plan_config['name']}")
        
    except Exception as e:
        logger.error(f"Erro ao fazer upgrade: {e}")
        raise


async def downgrade_user_to_suspended(user_id: str, reason: str):
    """Suspende a conta do usuário (sem acesso a nenhuma funcionalidade)"""
    try:
        db = SupabaseService()
        
        # Usar plan_type='suspended' como marcador (não temos coluna subscription_status)
        db.client.table('user_quotas').update({
            'plan_type': 'suspended',
            'plan_name': 'Conta Suspensa',
            'leads_limit': 0,
            'campaigns_limit': 0,
            'messages_limit': 0,
            'subscription_id': None,
            'updated_at': datetime.now().isoformat()
        }).eq('user_id', user_id).execute()
        
        logger.info(f"⚠️ Usuário {user_id} suspenso. Motivo: {reason}")
        
    except Exception as e:
        logger.error(f"Erro ao suspender conta: {e}")
        raise


async def log_webhook_event(event_type: str, payload: Dict[str, Any], status: str, error: Optional[str] = None):
    """Registra evento de webhook para auditoria"""
    try:
        db = SupabaseService()
        db.client.table('webhook_logs').insert({
            'event_type': event_type,
            'payload': payload,
            'status': status,
            'error_message': error,
            'created_at': datetime.now().isoformat()
        }).execute()
    except Exception as e:
        logger.error(f"Erro ao logar webhook: {e}")


@webhook_router.post("/webhook/kiwify")
async def kiwify_webhook(
    request: Request,
    x_kiwify_signature: Optional[str] = Header(None)
):
    """
    Endpoint para receber webhooks do Kiwify
    """
    try:
        body = await request.body()
        
        if not x_kiwify_signature:
            logger.warning("⚠️ Webhook Kiwify sem assinatura - rejeitado")
            await log_webhook_event('missing_signature', {}, 'failed', 'Missing signature header')
            raise HTTPException(status_code=401, detail="Missing X-Kiwify-Signature header")
        
        if not verify_kiwify_signature(body, x_kiwify_signature):
            logger.warning("⚠️ Assinatura inválida do webhook Kiwify")
            await log_webhook_event('invalid_signature', {}, 'failed', 'Invalid signature')
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        payload_dict = await request.json()
        payload = KiwifyWebhookPayload(**payload_dict)
        
        logger.info(f"📩 Webhook recebido: {payload.event_type} - {payload.customer_email}")
        
        # 1. Tentar buscar usuário existente
        existing_user = await get_user_by_email(payload.customer_email)
        
        user_id = None
        new_password = None
        is_new_user = False
        
        if existing_user:
            user_id = existing_user['id']
            logger.info(f"👤 Usuário existente encontrado: {user_id}")
        else:
            # 2. Se não existe e for pagamento aprovado, criar conta!
            if payload.event_type == 'order.paid':
                try:
                    new_user_data = await create_new_user(payload.customer_email, payload.customer_name)
                    user_id = new_user_data['id']
                    new_password = new_user_data['password']
                    is_new_user = True
                    logger.info(f"✨ Nova conta criada com sucesso: {user_id}")
                except Exception as e:
                    logger.error(f"Falha crítica ao criar usuário: {e}")
                    raise HTTPException(status_code=500, detail="Failed to create user account")
            else:
                # Se for cancelamento/reembolso de user que não existe, ignora
                logger.warning(f"⚠️ Evento {payload.event_type} para usuário inexistente ignorado.")
                return {"status": "ignored", "message": "User not found"}
        
        # Processar evento
        if payload.event_type == 'order.paid':
            # PAGAMENTO APROVADO - UPGRADE
            product_name_lower = payload.product_name.lower().strip()
            plan_key = PLAN_NAME_MAP.get(product_name_lower)
            
            if not plan_key:
                for name, key in PLAN_NAME_MAP.items():
                    if name in product_name_lower:
                        plan_key = key
                        break
            
            if not plan_key:
                plan_key = 'basico'
            
            # Atualiza ou Insere a cota (Upsert)
            await upgrade_user_to_plan(
                user_id=user_id,
                plan=plan_key,
                subscription_id=payload.subscription_id or payload.order_id,
                order_id=payload.order_id
            )
            
            # ENVIAR EMAIL
            try:
                plan_config = PLAN_LIMITS.get(plan_key, {})
                email_service = get_email_service()
                
                # Montar lista de features do plano
                features = []
                if plan_config.get('leads_limit') == -1:
                    features.append("Buscas de leads ilimitadas")
                if plan_config.get('campaigns_limit', 0) == -1:
                    features.append("Disparador WhatsApp ilimitado")
                if plan_key == 'avancado':
                    features.append("Agente IA para atendimento automático")
                    features.append("Múltiplas instâncias WhatsApp")
                
                # URL de login (usar variável de ambiente ou padrão)
                login_url = os.environ.get('FRONTEND_URL', 'https://app.client4you.com.br') + '/login'
                
                if is_new_user and new_password:
                    # NOVO USUÁRIO: Email especial com credenciais em destaque
                    await email_service.send_welcome_with_credentials(
                        user_email=payload.customer_email,
                        user_name=payload.customer_name,
                        temp_password=new_password,
                        plan_name=plan_config.get('name', plan_key),
                        plan_features=features,
                        order_id=payload.order_id,
                        login_url=login_url
                    )
                    logger.info(f"📧 Email de boas-vindas COM CREDENCIAIS enviado para {payload.customer_email}")
                else:
                    # USUÁRIO EXISTENTE: Email normal de upgrade
                    await email_service.send_purchase_confirmation(
                        user_email=payload.customer_email,
                        user_name=payload.customer_name,
                        plan_name=plan_config.get('name', plan_key),
                        plan_features=features,
                        order_id=payload.order_id
                    )
                    logger.info(f"📧 Email de upgrade enviado para {payload.customer_email}")
                
            except Exception as e:
                logger.error(f"❌ Erro ao enviar email: {e}")
            
            await log_webhook_event(payload.event_type, payload_dict, 'success')
            
            return {
                "status": "success",
                "message": "User processed successfully",
                "is_new_user": is_new_user
            }
        
        elif payload.event_type in ['order.refunded', 'subscription.canceled']:
            # REEMBOLSO/CANCELAMENTO - SUSPENDER CONTA
            await downgrade_user_to_suspended(
                user_id=user_id,
                reason=f'Evento: {payload.event_type}'
            )
            await log_webhook_event(payload.event_type, payload_dict, 'success')
            return {"status": "success", "message": "User suspended"}
        
        else:
            return {"status": "ignored", "message": f"Unknown event: {payload.event_type}"}
    
    except Exception as e:
        logger.error(f"❌ Erro no webhook: {e}")
        await log_webhook_event('error', {}, 'failed', str(e))
        raise HTTPException(status_code=500, detail=str(e))

@webhook_router.get("/webhook/test")
async def test_webhook():
    return {"status": "ok", "message": "Webhook V2 (Auto-Create) Active"}