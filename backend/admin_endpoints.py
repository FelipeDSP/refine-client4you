"""
Admin endpoints - Gerenciamento de usuários
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
import logging
from security_utils import get_authenticated_user, require_role
from supabase_service import get_supabase_service
from audit_service import get_audit_service

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


class DeleteUserRequest(BaseModel):
    user_id: str


class CleanupOrphansResponse(BaseModel):
    orphans_found: int
    orphans_deleted: int
    orphan_emails: list[str]


class SuspendUserRequest(BaseModel):
    reason: Optional[str] = "Suspenso pelo administrador"


class ActivateUserRequest(BaseModel):
    plan_type: str = "basico"
    plan_name: str = "Plano Básico"
    days_valid: int = 30


@admin_router.post("/users/{user_id}/suspend")
async def suspend_user_account(
    request: Request,
    user_id: str,
    suspend_data: SuspendUserRequest,
    auth_user: dict = Depends(require_role("super_admin"))
):
    """
    Suspende a conta de um usuário (bloqueia acesso a todas as funcionalidades)
    
    IMPORTANTE: Requer role super_admin
    """
    try:
        # Prevenir auto-suspensão
        if user_id == auth_user["user_id"]:
            raise HTTPException(
                status_code=400,
                detail="Você não pode suspender sua própria conta"
            )
        
        db = get_supabase_service()
        audit = get_audit_service()
        
        # Buscar dados do usuário
        profile = db.client.table('profiles')\
            .select('email')\
            .eq('id', user_id)\
            .single()\
            .execute()
        
        if not profile.data:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
        target_email = profile.data.get('email')
        
        # Suspender conta (usando plan_type='suspended' como marcador)
        from datetime import datetime
        db.client.table('user_quotas').upsert({
            'user_id': user_id,
            'plan_type': 'suspended',
            'plan_name': 'Conta Suspensa',
            'leads_limit': 0,
            'campaigns_limit': 0,
            'messages_limit': 0,
            'updated_at': datetime.now().isoformat()
        }, on_conflict='user_id').execute()
        
        # Log de auditoria
        await audit.log_action(
            user_id=auth_user['user_id'],
            user_email=auth_user['email'],
            action='user_suspended',
            target_type='user',
            target_id=user_id,
            target_email=target_email,
            details={'reason': suspend_data.reason},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get('user-agent')
        )
        
        logger.info(f"Admin {auth_user['email']} suspendeu usuário {target_email}")
        
        return {
            "success": True,
            "message": f"Conta de {target_email} suspensa com sucesso",
            "user_id": user_id,
            "status": "suspended"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao suspender usuário: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao suspender: {str(e)}")


@admin_router.post("/users/{user_id}/activate")
async def activate_user_account(
    request: Request,
    user_id: str,
    activate_data: ActivateUserRequest,
    auth_user: dict = Depends(require_role("super_admin"))
):
    """
    Ativa/reativa a conta de um usuário com um plano específico
    
    IMPORTANTE: Requer role super_admin
    """
    try:
        db = get_supabase_service()
        audit = get_audit_service()
        
        # Buscar dados do usuário
        profile = db.client.table('profiles')\
            .select('email, company_id')\
            .eq('id', user_id)\
            .single()\
            .execute()
        
        if not profile.data:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
        target_email = profile.data.get('email')
        company_id = profile.data.get('company_id')
        
        # Validar plano
        valid_plans = ['basico', 'intermediario', 'avancado']
        plan_type = activate_data.plan_type.lower()
        if plan_type not in valid_plans:
            raise HTTPException(
                status_code=400, 
                detail=f"Plano inválido. Use: {', '.join(valid_plans)}"
            )
        
        # Configurar limites por plano
        plan_configs = {
            'basico': {'leads_limit': -1, 'campaigns_limit': 0, 'messages_limit': 0},
            'intermediario': {'leads_limit': -1, 'campaigns_limit': -1, 'messages_limit': -1},
            'avancado': {'leads_limit': -1, 'campaigns_limit': -1, 'messages_limit': -1},
        }
        
        from datetime import datetime, timedelta
        expires_at = (datetime.now() + timedelta(days=activate_data.days_valid)).isoformat()
        
        # Ativar conta (usando apenas colunas existentes na tabela user_quotas)
        db.client.table('user_quotas').upsert({
            'user_id': user_id,
            'company_id': company_id,
            'plan_type': plan_type,
            'plan_name': activate_data.plan_name,
            'leads_limit': plan_configs[plan_type]['leads_limit'],
            'campaigns_limit': plan_configs[plan_type]['campaigns_limit'],
            'messages_limit': plan_configs[plan_type]['messages_limit'],
            'leads_used': 0,
            'campaigns_used': 0,
            'messages_sent': 0,
            'plan_expires_at': expires_at,
            'updated_at': datetime.now().isoformat()
        }, on_conflict='user_id').execute()
        
        # Log de auditoria
        await audit.log_action(
            user_id=auth_user['user_id'],
            user_email=auth_user['email'],
            action='user_activated',
            target_type='user',
            target_id=user_id,
            target_email=target_email,
            details={
                'plan_type': plan_type,
                'plan_name': activate_data.plan_name,
                'expires_at': expires_at
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get('user-agent')
        )
        
        logger.info(f"Admin {auth_user['email']} ativou usuário {target_email} com plano {plan_type}")
        
        return {
            "success": True,
            "message": f"Conta de {target_email} ativada com plano {activate_data.plan_name}",
            "user_id": user_id,
            "plan_type": plan_type,
            "expires_at": expires_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao ativar usuário: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao ativar: {str(e)}")


@admin_router.get("/users")
async def list_all_users(
    auth_user: dict = Depends(require_role("super_admin")),
    limit: int = 50,
    offset: int = 0
):
    """
    Lista todos os usuários com seus planos e status
    
    IMPORTANTE: Requer role super_admin
    """
    try:
        db = get_supabase_service()
        
        # Buscar profiles com quotas (LEFT JOIN simulado)
        profiles_result = db.client.table('profiles')\
            .select('id, email, full_name, company_id, created_at')\
            .order('created_at', desc=True)\
            .range(offset, offset + limit - 1)\
            .execute()
        
        users = []
        for profile in (profiles_result.data or []):
            user_id = profile['id']
            
            # Buscar quota do usuário
            quota_result = db.client.table('user_quotas')\
                .select('plan_type, plan_name, subscription_status, plan_expires_at')\
                .eq('user_id', user_id)\
                .maybe_single()\
                .execute()
            
            quota = quota_result.data if quota_result.data else {}
            
            users.append({
                'id': user_id,
                'email': profile['email'],
                'full_name': profile.get('full_name'),
                'company_id': profile.get('company_id'),
                'plan_type': quota.get('plan_type', 'sem_plano'),
                'plan_name': quota.get('plan_name', 'Sem Plano'),
                'status': quota.get('subscription_status', 'inactive'),
                'expires_at': quota.get('plan_expires_at'),
                'created_at': profile['created_at']
            })
        
        # Contar total
        count_result = db.client.table('profiles')\
            .select('id', count='exact')\
            .execute()
        
        return {
            'users': users,
            'total': count_result.count or len(users),
            'limit': limit,
            'offset': offset
        }
        
    except Exception as e:
        logger.error(f"Erro ao listar usuários: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao listar: {str(e)}")




@admin_router.get("/orphan-users")
async def get_orphan_users(
    auth_user: dict = Depends(require_role("super_admin"))
):
    """
    Lista usuários órfãos (existem em auth.users mas não em profiles)
    
    IMPORTANTE: Requer role super_admin
    """
    try:
        db = get_supabase_service()
        
        # Buscar todos os usuários do Auth
        auth_response = db.client.auth.admin.list_users()
        auth_users = auth_response if isinstance(auth_response, list) else []
        
        # Buscar todos os IDs de profiles
        profiles_result = db.client.table('profiles').select('id').execute()
        profile_ids = set([p['id'] for p in profiles_result.data]) if profiles_result.data else set()
        
        # Encontrar órfãos
        orphans = []
        for user in auth_users:
            user_id = user.id if hasattr(user, 'id') else user.get('id')
            email = user.email if hasattr(user, 'email') else user.get('email')
            created_at = user.created_at if hasattr(user, 'created_at') else user.get('created_at')
            
            if user_id not in profile_ids:
                orphans.append({
                    'id': user_id,
                    'email': email,
                    'created_at': created_at
                })
        
        logger.info(f"Admin {auth_user['email']} listou {len(orphans)} usuários órfãos")
        
        return {
            'total_auth_users': len(auth_users),
            'total_profiles': len(profile_ids),
            'orphans_found': len(orphans),
            'orphans': orphans
        }
        
    except Exception as e:
        logger.error(f"Erro ao listar usuários órfãos: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao listar órfãos: {str(e)}")


@admin_router.delete("/orphan-users")
async def cleanup_orphan_users(
    auth_user: dict = Depends(require_role("super_admin"))
):
    """
    Remove todos os usuários órfãos (existem em auth.users mas não em profiles)
    
    ATENÇÃO: Ação irreversível!
    IMPORTANTE: Requer role super_admin
    """
    try:
        db = get_supabase_service()
        
        # Buscar órfãos (mesmo código do endpoint GET)
        auth_response = db.client.auth.admin.list_users()
        auth_users = auth_response if isinstance(auth_response, list) else []
        
        profiles_result = db.client.table('profiles').select('id').execute()
        profile_ids = set([p['id'] for p in profiles_result.data]) if profiles_result.data else set()
        
        orphans = []
        for user in auth_users:
            user_id = user.id if hasattr(user, 'id') else user.get('id')
            email = user.email if hasattr(user, 'email') else user.get('email')
            
            if user_id not in profile_ids:
                orphans.append({'id': user_id, 'email': email})
        
        if not orphans:
            return {
                'success': True,
                'message': 'Nenhum usuário órfão encontrado',
                'orphans_deleted': 0,
                'orphan_emails': []
            }
        
        # Deletar órfãos
        deleted_count = 0
        deleted_emails = []
        failed = []
        
        for orphan in orphans:
            try:
                db.client.auth.admin.delete_user(orphan['id'])
                deleted_count += 1
                deleted_emails.append(orphan['email'])
                logger.info(f"✅ Órfão deletado: {orphan['email']} (ID: {orphan['id']})")
            except Exception as e:
                failed.append({'email': orphan['email'], 'error': str(e)})
                logger.error(f"❌ Erro ao deletar órfão {orphan['email']}: {e}")
        
        logger.warning(f"Admin {auth_user['email']} deletou {deleted_count} usuários órfãos")
        
        return {
            'success': True,
            'message': f'{deleted_count} usuário(s) órfão(s) deletado(s)',
            'orphans_found': len(orphans),
            'orphans_deleted': deleted_count,
            'orphan_emails': deleted_emails,
            'failed': failed if failed else None
        }
        
    except Exception as e:
        logger.error(f"Erro ao limpar usuários órfãos: {e}")
        raise HTTPException(status_code=500, detail=f"Erro na limpeza: {str(e)}")


class UpdateQuotaRequest(BaseModel):
    plan_type: str
    plan_name: str
    leads_limit: int
    campaigns_limit: int
    messages_limit: int


@admin_router.get("/users/{user_id}/quota")
async def get_user_quota(
    user_id: str,
    auth_user: dict = Depends(require_role("super_admin"))
):
    """
    Busca quota de um usuário específico (admin only)
    
    IMPORTANTE: Requer role super_admin
    """
    try:
        db = get_supabase_service()
        
        # Buscar quota do usuário usando service_role (bypassa RLS)
        quota_result = db.client.table('user_quotas')\
            .select('*')\
            .eq('user_id', user_id)\
            .single()\
            .execute()
        
        if not quota_result.data:
            # Retornar valores default se não houver quota
            return {
                'user_id': user_id,
                'plan_type': 'demo',
                'plan_name': 'Demo',
                'leads_limit': 5,
                'campaigns_limit': 1,
                'messages_limit': 0,
                'leads_used': 0,
                'campaigns_used': 0,
                'messages_used': 0
            }
        
        logger.info(f"Admin {auth_user['email']} consultou quota de {user_id}")
        return quota_result.data
        
    except Exception as e:
        logger.error(f"Erro ao buscar quota: {e}")
        # Retornar valores default em caso de erro
        return {
            'user_id': user_id,
            'plan_type': 'demo',
            'plan_name': 'Demo',
            'leads_limit': 5,
            'campaigns_limit': 1,
            'messages_limit': 0
        }


@admin_router.post("/users/{user_id}/quota")
async def update_user_quota(
    request: Request,
    user_id: str,
    quota_data: UpdateQuotaRequest,
    auth_user: dict = Depends(require_role("super_admin"))
):
    """
    Atualiza quota de um usuário (admin only)
    
    IMPORTANTE: Requer role super_admin
    """
    try:
        db = get_supabase_service()
        audit = get_audit_service()
        
        # Buscar user_id para pegar company_id e email
        profile = db.client.table('profiles')\
            .select('company_id, email')\
            .eq('id', user_id)\
            .single()\
            .execute()
        
        if not profile.data:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
        company_id = profile.data.get('company_id')
        target_email = profile.data.get('email')
        
        # Upsert quota
        quota_dict = {
            'user_id': user_id,
            'company_id': company_id,
            'plan_type': quota_data.plan_type,
            'plan_name': quota_data.plan_name,
            'leads_limit': quota_data.leads_limit,
            'campaigns_limit': quota_data.campaigns_limit,
            'messages_limit': quota_data.messages_limit
        }
        
        result = db.client.table('user_quotas')\
            .upsert(quota_dict, on_conflict='user_id')\
            .execute()
        
        # LOG DE AUDITORIA
        await audit.log_action(
            user_id=auth_user['user_id'],
            user_email=auth_user['email'],
            action='quota_updated',
            target_type='quota',
            target_id=user_id,
            target_email=target_email,
            details={
                'plan_type': quota_data.plan_type,
                'plan_name': quota_data.plan_name,
                'leads_limit': quota_data.leads_limit,
                'campaigns_limit': quota_data.campaigns_limit,
                'messages_limit': quota_data.messages_limit
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get('user-agent')
        )
        
        logger.info(f"Admin {auth_user['email']} atualizou quota de {user_id} para {quota_data.plan_type}")
        
        return {
            'success': True,
            'message': 'Quota atualizada com sucesso',
            'quota': result.data[0] if result.data else quota_dict
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar quota: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar quota: {str(e)}")


@admin_router.delete("/users/{user_id}")
async def delete_user_completely(
    request: Request,
    user_id: str,
    auth_user: dict = Depends(require_role("super_admin"))
):
    """
    Deleta completamente um usuário do sistema
    - Remove de auth.users (Supabase Auth)
    - Remove de profiles
    - Remove de user_roles
    - Remove de user_quotas
    - Remove todas as dependências
    
    IMPORTANTE: Requer role super_admin
    """
    try:
        # Prevenir auto-deleção
        if user_id == auth_user["user_id"]:
            raise HTTPException(
                status_code=400,
                detail="Você não pode deletar sua própria conta de admin"
            )
        
        db = get_supabase_service()
        audit = get_audit_service()
        
        # 1. Buscar dados do usuário antes de deletar (com maybe_single para evitar erro se não existir)
        user_profile = db.client.table('profiles')\
            .select('email, company_id')\
            .eq('id', user_id)\
            .maybe_single()\
            .execute()
        
        # Se profile não existe, verificar se usuário existe no auth
        if not user_profile.data:
            # Tentar buscar direto no auth
            try:
                auth_user_data = db.client.auth.admin.get_user_by_id(user_id)
                if auth_user_data and auth_user_data.user:
                    user_email = auth_user_data.user.email
                    company_id = None
                else:
                    raise HTTPException(status_code=404, detail="Usuário não encontrado no sistema")
            except:
                raise HTTPException(status_code=404, detail="Usuário não encontrado")
        else:
            user_email = user_profile.data.get('email')
            company_id = user_profile.data.get('company_id')
        
        logger.info(f"Admin {auth_user['email']} iniciando deleção de usuário {user_email} (ID: {user_id})")
        
        # 2. Deletar user_quotas
        try:
            db.client.table('user_quotas').delete().eq('user_id', user_id).execute()
            logger.info(f"✅ user_quotas deletado para {user_id}")
        except Exception as e:
            logger.warning(f"Erro ao deletar user_quotas: {e}")
        
        # 3. Deletar user_roles
        try:
            db.client.table('user_roles').delete().eq('user_id', user_id).execute()
            logger.info(f"✅ user_roles deletado para {user_id}")
        except Exception as e:
            logger.warning(f"Erro ao deletar user_roles: {e}")
        
        # 4. Deletar campanhas do usuário (se houver)
        try:
            campaigns = db.client.table('campaigns')\
                .select('id')\
                .eq('user_id', user_id)\
                .execute()
            
            if campaigns.data:
                for campaign in campaigns.data:
                    # Deletar contatos e logs da campanha
                    db.client.table('campaign_contacts')\
                        .delete()\
                        .eq('campaign_id', campaign['id'])\
                        .execute()
                    db.client.table('message_logs')\
                        .delete()\
                        .eq('campaign_id', campaign['id'])\
                        .execute()
                
                # Deletar campanhas
                db.client.table('campaigns').delete().eq('user_id', user_id).execute()
                logger.info(f"✅ Campanhas deletadas para {user_id}")
        except Exception as e:
            logger.warning(f"Erro ao deletar campanhas: {e}")
        
        # 5. Deletar leads do usuário
        try:
            db.client.table('leads').delete().eq('user_id', user_id).execute()
            logger.info(f"✅ Leads deletados para {user_id}")
        except Exception as e:
            logger.warning(f"Erro ao deletar leads: {e}")
        
        # 6. Deletar histórico de busca
        try:
            db.client.table('search_history').delete().eq('user_id', user_id).execute()
            logger.info(f"✅ Histórico de busca deletado para {user_id}")
        except Exception as e:
            logger.warning(f"Erro ao deletar search_history: {e}")
        
        # 7. Deletar notificações
        try:
            db.client.table('notifications').delete().eq('user_id', user_id).execute()
            logger.info(f"✅ Notificações deletadas para {user_id}")
        except Exception as e:
            logger.warning(f"Erro ao deletar notificações: {e}")
        
        # 8. Deletar profile
        db.client.table('profiles').delete().eq('id', user_id).execute()
        logger.info(f"✅ Profile deletado para {user_id}")
        
        # 9. CRÍTICO: Deletar da tabela auth.users usando admin API
        try:
            # Usar service_role para deletar usuário do Auth
            response = db.client.auth.admin.delete_user(user_id)
            logger.info(f"✅ Usuário deletado do Supabase Auth: {user_id}")
        except Exception as e:
            error_msg = str(e)
            # Se o usuário não foi encontrado ou já foi deletado, considerar sucesso
            if "not found" in error_msg.lower() or "user not allowed" in error_msg.lower():
                logger.warning(f"⚠️ Usuário já removido do auth ou sem permissão: {user_id}")
            else:
                logger.error(f"❌ ERRO ao deletar do auth.users: {e}")
                # Não levantar exceção, pois já deletamos do banco
        
        # LOG DE AUDITORIA
        await audit.log_action(
            user_id=auth_user['user_id'],
            user_email=auth_user['email'],
            action='user_deleted',
            target_type='user',
            target_id=user_id,
            target_email=user_email,
            details={
                'company_id': company_id
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get('user-agent')
        )
        
        logger.info(f"✅ DELEÇÃO COMPLETA: Usuário {user_email} (ID: {user_id}) totalmente removido")
        
        return {
            "success": True,
            "message": f"Usuário {user_email} deletado completamente do sistema",
            "user_id": user_id,
            "email": user_email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao deletar usuário {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao deletar usuário: {str(e)}"
        )
