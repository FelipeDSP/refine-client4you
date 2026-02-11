#!/usr/bin/env python3
"""
Script para limpar usuários órfãos do Supabase Auth
Identifica e remove usuários que existem em auth.users mas não em profiles
"""
import sys
sys.path.append('/app/backend')

import os
from dotenv import load_dotenv
from supabase import create_client
import asyncio

load_dotenv('/app/backend/.env')

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("❌ Erro: SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY devem estar configurados")
    sys.exit(1)

# Cliente com service_role (tem acesso a auth.users)
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def get_auth_users():
    """Busca todos os usuários de auth.users"""
    try:
        # Listar usuários do Auth (paginação manual se necessário)
        response = supabase.auth.admin.list_users()
        return response if isinstance(response, list) else []
    except Exception as e:
        print(f"❌ Erro ao buscar usuários do Auth: {e}")
        return []


def get_profile_user_ids():
    """Busca todos os IDs de profiles"""
    try:
        result = supabase.table('profiles').select('id').execute()
        return set([p['id'] for p in result.data]) if result.data else set()
    except Exception as e:
        print(f"❌ Erro ao buscar profiles: {e}")
        return set()


def find_orphan_users():
    """Encontra usuários órfãos (em auth.users mas não em profiles)"""
    print("=" * 70)
    print("🔍 BUSCANDO USUÁRIOS ÓRFÃOS")
    print("=" * 70)
    print()
    
    # Buscar usuários do auth
    print("📋 Buscando usuários de auth.users...")
    auth_users = get_auth_users()
    print(f"   Total em auth.users: {len(auth_users)}")
    
    # Buscar IDs de profiles
    print("📋 Buscando usuários de profiles...")
    profile_ids = get_profile_user_ids()
    print(f"   Total em profiles: {len(profile_ids)}")
    print()
    
    # Encontrar órfãos
    orphans = []
    for user in auth_users:
        user_id = user.id if hasattr(user, 'id') else user.get('id')
        if user_id not in profile_ids:
            orphans.append(user)
    
    return orphans


def display_orphans(orphans):
    """Exibe lista de usuários órfãos"""
    if not orphans:
        print("✅ Nenhum usuário órfão encontrado!")
        print("   O banco está limpo.")
        return
    
    print("=" * 70)
    print(f"⚠️  ENCONTRADOS {len(orphans)} USUÁRIOS ÓRFÃOS")
    print("=" * 70)
    print()
    print("Estes usuários existem em auth.users mas NÃO em profiles:")
    print()
    
    for i, user in enumerate(orphans, 1):
        user_id = user.id if hasattr(user, 'id') else user.get('id')
        email = user.email if hasattr(user, 'email') else user.get('email', 'N/A')
        created_at = user.created_at if hasattr(user, 'created_at') else user.get('created_at', 'N/A')
        
        print(f"{i}. Email: {email}")
        print(f"   ID: {user_id}")
        print(f"   Criado em: {created_at}")
        print()


def delete_orphan_users(orphans):
    """Deleta usuários órfãos de auth.users"""
    if not orphans:
        return 0
    
    print("=" * 70)
    print("🗑️  DELETANDO USUÁRIOS ÓRFÃOS")
    print("=" * 70)
    print()
    
    deleted_count = 0
    failed_count = 0
    
    for user in orphans:
        user_id = user.id if hasattr(user, 'id') else user.get('id')
        email = user.email if hasattr(user, 'email') else user.get('email', 'N/A')
        
        try:
            supabase.auth.admin.delete_user(user_id)
            print(f"✅ Deletado: {email} (ID: {user_id})")
            deleted_count += 1
        except Exception as e:
            print(f"❌ Erro ao deletar {email}: {e}")
            failed_count += 1
    
    print()
    print("=" * 70)
    print("📊 RESUMO DA LIMPEZA")
    print("=" * 70)
    print(f"✅ Deletados com sucesso: {deleted_count}")
    if failed_count > 0:
        print(f"❌ Falharam: {failed_count}")
    print()
    
    return deleted_count


def main():
    print()
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║                                                                   ║")
    print("║          🧹 LIMPEZA DE USUÁRIOS ÓRFÃOS - SUPABASE AUTH           ║")
    print("║                                                                   ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()
    
    # Buscar órfãos
    orphans = find_orphan_users()
    
    # Exibir lista
    display_orphans(orphans)
    
    if not orphans:
        return
    
    # Confirmar deleção
    print()
    print("⚠️  ATENÇÃO: Esta ação é IRREVERSÍVEL!")
    print("   Os emails serão liberados para reuso.")
    print()
    
    response = input("Deseja deletar TODOS os usuários órfãos? (digite 'SIM' para confirmar): ")
    
    if response.strip().upper() == "SIM":
        print()
        deleted = delete_orphan_users(orphans)
        
        if deleted > 0:
            print("✅ Limpeza concluída com sucesso!")
            print(f"   {deleted} usuário(s) removido(s) de auth.users")
            print("   Emails agora estão livres para reuso.")
        else:
            print("⚠️  Nenhum usuário foi deletado.")
    else:
        print()
        print("❌ Operação cancelada pelo usuário.")
        print("   Nenhum usuário foi deletado.")
    
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print("❌ Operação cancelada pelo usuário (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        sys.exit(1)
