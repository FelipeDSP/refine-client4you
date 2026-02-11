#!/usr/bin/env python3
"""
Teste: Gerar token de teste para verificar roles
"""
import sys
sys.path.append('/app/backend')

from fastapi import Request
from security_utils import get_authenticated_user
import asyncio

# Simular request com token
class MockRequest:
    def __init__(self, token):
        self.headers = {"Authorization": f"Bearer {token}"}
        self.url = type('obj', (object,), {'path': '/api/admin/test'})()

async def test_token(token):
    try:
        request = MockRequest(token)
        user = await get_authenticated_user(request)
        print("✅ Token válido!")
        print(f"   User ID: {user['user_id']}")
        print(f"   Email: {user['email']}")
        print(f"   Role: {user['role']}")
        print(f"   All roles: {user.get('roles', [])}")
        return True
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

if __name__ == "__main__":
    print("Para testar, execute no navegador:")
    print()
    print("1. Abra DevTools (F12)")
    print("2. Vá em Console")
    print("3. Execute:")
    print()
    print("   const { data } = await supabase.auth.getSession();")
    print("   console.log(data.session.access_token);")
    print()
    print("4. Copie o token e execute:")
    print("   python3 test_token.py SEU_TOKEN_AQUI")
