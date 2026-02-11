#!/usr/bin/env python3
"""
Verificação rápida de órfãos (apenas conta, não deleta)
"""
import sys
sys.path.append('/app/backend')

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('/app/backend/.env')

supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_SERVICE_ROLE_KEY')
)

print("🔍 Verificando usuários órfãos...")
print()

# Auth users
auth_response = supabase.auth.admin.list_users()
auth_users = auth_response if isinstance(auth_response, list) else []
print(f"📊 Total em auth.users: {len(auth_users)}")

# Profile IDs
profiles_result = supabase.table('profiles').select('id').execute()
profile_ids = set([p['id'] for p in profiles_result.data]) if profiles_result.data else set()
print(f"📊 Total em profiles: {len(profile_ids)}")

# Órfãos
orphans = []
for user in auth_users:
    user_id = user.id if hasattr(user, 'id') else user.get('id')
    email = user.email if hasattr(user, 'email') else user.get('email')
    if user_id not in profile_ids:
        orphans.append(email)

print()
if orphans:
    print(f"⚠️  Órfãos encontrados: {len(orphans)}")
    print()
    for email in orphans:
        print(f"   - {email}")
    print()
    print("💡 Execute: python3 cleanup_orphan_users.py")
else:
    print("✅ Nenhum órfão! Banco limpo.")
print()
