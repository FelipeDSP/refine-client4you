"""
Admin Access Control Middleware
Middleware para proteger acesso ao painel administrativo
"""
import os
import logging
from datetime import datetime
from typing import Optional, Tuple
from fastapi import HTTPException, Request
from supabase_service import get_supabase_service
from audit_service import get_audit_service

logger = logging.getLogger(__name__)


class AdminAccessControl:
    """Controle de acesso ao painel administrativo"""
    
    def __init__(self):
        # Whitelist de IPs (opcional, via env var)
        whitelist_str = os.getenv('ADMIN_IP_WHITELIST', '')
        self.ip_whitelist = [ip.strip() for ip in whitelist_str.split(',') if ip.strip()]
        
        # Se whitelist vazia, não restringe por IP
        self.ip_restriction_enabled = len(self.ip_whitelist) > 0
        
        if self.ip_restriction_enabled:
            logger.info(f"🔒 IP Whitelist ativada com {len(self.ip_whitelist)} IPs")
        else:
            logger.info("⚠️ IP Whitelist DESATIVADA - todos IPs permitidos")
    
    async def check_ip_allowed(self, ip_address: str, company_id: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Verifica se IP está autorizado a acessar admin
        
        Args:
            ip_address: IP da requisição
            company_id: ID da empresa (para whitelist por empresa)
        
        Returns:
            (allowed: bool, reason: str)
        """
        # Se IP whitelist global está desabilitada, permitir
        if not self.ip_restriction_enabled:
            return True, None
        
        # Verificar whitelist global (.env)
        if ip_address in self.ip_whitelist:
            logger.info(f"✅ IP {ip_address} autorizado (whitelist global)")
            return True, None
        
        # Verificar whitelist da empresa (banco de dados)
        if company_id:
            try:
                db = get_supabase_service()
                result = db.client.table('ip_whitelist')\
                    .select('*')\
                    .eq('company_id', company_id)\
                    .eq('enabled', True)\
                    .execute()
                
                if result.data:
                    for entry in result.data:
                        allowed_ip = entry.get('ip_address', '')
                        
                        # Suporte para CIDR (ex: 192.168.1.0/24)
                        if '/' in allowed_ip:
                            # TODO: Implementar verificação CIDR
                            pass
                        else:
                            # Match exato
                            if ip_address == allowed_ip:
                                logger.info(f"✅ IP {ip_address} autorizado (whitelist empresa {company_id})")
                                return True, None
            
            except Exception as e:
                logger.error(f"❌ Erro ao verificar IP whitelist: {e}")
        
        # IP não autorizado
        logger.warning(f"🚫 IP {ip_address} NÃO autorizado para acessar admin")
        return False, f"IP {ip_address} não autorizado para acesso administrativo"
    
    async def log_admin_access(
        self,
        user_id: str,
        user_email: str,
        action: str,
        ip_address: str,
        user_agent: str,
        success: bool = True,
        reason: Optional[str] = None
    ):
        """
        Registra tentativa de acesso ao painel admin
        
        Args:
            user_id: ID do usuário
            user_email: Email do usuário
            action: Ação realizada (ex: 'admin_panel_access')
            ip_address: IP da requisição
            user_agent: User-Agent
            success: Se acesso foi bem-sucedido
            reason: Motivo de falha (se aplicável)
        """
        try:
            audit = get_audit_service()
            
            await audit.log_action(
                user_id=user_id,
                user_email=user_email,
                action=action,
                target_type='settings',
                target_id=None,
                target_email=None,
                details={
                    'success': success,
                    'reason': reason,
                    'timestamp': datetime.utcnow().isoformat()
                },
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            if success:
                logger.info(f"✅ Admin access logged: {user_email} from {ip_address}")
            else:
                logger.warning(f"❌ Admin access DENIED logged: {user_email} from {ip_address} - {reason}")
        
        except Exception as e:
            logger.error(f"❌ Erro ao registrar acesso admin: {e}")
    
    async def verify_admin_access(
        self,
        request: Request,
        user_id: str,
        user_email: str,
        company_id: Optional[str] = None
    ) -> bool:
        """
        Verifica se usuário pode acessar painel admin
        
        Retorna True se permitido, raise HTTPException se não
        """
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Verificar IP whitelist
        ip_allowed, ip_reason = await self.check_ip_allowed(ip_address, company_id)
        
        if not ip_allowed:
            # Log de acesso negado
            await self.log_admin_access(
                user_id=user_id,
                user_email=user_email,
                action='admin_panel_access_denied',
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                reason=ip_reason
            )
            
            raise HTTPException(
                status_code=403,
                detail=f"Acesso negado: {ip_reason}"
            )
        
        # Log de acesso bem-sucedido
        await self.log_admin_access(
            user_id=user_id,
            user_email=user_email,
            action='admin_panel_access',
            ip_address=ip_address,
            user_agent=user_agent,
            success=True
        )
        
        return True


# Singleton global
_admin_access_control = None

def get_admin_access_control() -> AdminAccessControl:
    """Retorna instância singleton do AdminAccessControl"""
    global _admin_access_control
    if _admin_access_control is None:
        _admin_access_control = AdminAccessControl()
    return _admin_access_control
