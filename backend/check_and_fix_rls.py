#!/usr/bin/env python3
"""
Check and fix RLS policies for backend operations
"""
import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# Load environment
load_dotenv('/app/backend/.env')

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    sys.exit(1)

print("=" * 70)
print("🔍 VERIFICANDO CONFIGURAÇÃO SUPABASE E RLS POLICIES")
print("=" * 70)
print(f"✅ SUPABASE_URL: {SUPABASE_URL}")
print(f"✅ SERVICE_ROLE_KEY: {SUPABASE_SERVICE_ROLE_KEY[:30]}...")
print()

# Create client with service role key (bypasses RLS)
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

print("=" * 70)
print("📊 TESTANDO ACESSO ÀS TABELAS")
print("=" * 70)

# Test 1: Check if campaigns table exists and is accessible
try:
    result = supabase.table('campaigns').select('*').limit(1).execute()
    print(f"✅ Tabela 'campaigns' acessível (service_role bypassa RLS)")
    print(f"   Registros na tabela: {len(result.data)}")
except Exception as e:
    print(f"❌ Erro ao acessar 'campaigns': {e}")

# Test 2: Check campaign_contacts
try:
    result = supabase.table('campaign_contacts').select('*').limit(1).execute()
    print(f"✅ Tabela 'campaign_contacts' acessível")
    print(f"   Registros na tabela: {len(result.data)}")
except Exception as e:
    print(f"❌ Erro ao acessar 'campaign_contacts': {e}")

# Test 3: Check message_logs
try:
    result = supabase.table('message_logs').select('*').limit(1).execute()
    print(f"✅ Tabela 'message_logs' acessível")
    print(f"   Registros na tabela: {len(result.data)}")
except Exception as e:
    print(f"❌ Erro ao acessar 'message_logs': {e}")

print()
print("=" * 70)
print("💡 INFORMAÇÃO IMPORTANTE")
print("=" * 70)
print("""
O backend está usando SUPABASE_SERVICE_ROLE_KEY que AUTOMATICAMENTE
bypassa todas as RLS policies. Isso significa:

✅ Backend pode fazer INSERT/UPDATE/DELETE em qualquer tabela
✅ Não precisa de policies específicas para service_role
✅ RLS policies só afetam chamadas do frontend (usando anon key)

Se houver erros de "RLS policy violation", provavelmente é porque:
1. O frontend está tentando inserir dados diretamente (não deve)
2. Algum código ainda está usando SUPABASE_KEY em vez de SERVICE_ROLE_KEY
3. As policies para usuários autenticados (auth.uid()) estão incorretas

RECOMENDAÇÃO: Todo INSERT/UPDATE/DELETE deve vir do backend via API.
""")

print()
print("=" * 70)
print("🧪 TESTANDO INSERT DE CAMPANHA (SIMULAÇÃO)")
print("=" * 70)

# Test creating a campaign (will work with service_role key)
test_campaign = {
    'company_id': '00000000-0000-0000-0000-000000000000',  # Fake UUID for test
    'user_id': None,
    'name': 'TEST - RLS Check (can be deleted)',
    'status': 'draft',
    'message_type': 'text',
    'message_text': 'Teste RLS',
    'total_contacts': 0,
    'sent_count': 0,
    'error_count': 0,
    'pending_count': 0
}

try:
    result = supabase.table('campaigns').insert(test_campaign).execute()
    if result.data:
        campaign_id = result.data[0]['id']
        print(f"✅ INSERT funcionou! Campaign ID: {campaign_id}")
        
        # Clean up - delete test campaign
        supabase.table('campaigns').delete().eq('id', campaign_id).execute()
        print(f"✅ Campanha de teste deletada (cleanup)")
    else:
        print("⚠️  INSERT retornou vazio mas não deu erro")
except Exception as e:
    print(f"❌ Erro ao inserir campanha: {e}")
    print("\n⚠️  ATENÇÃO: O backend deveria conseguir inserir com service_role key!")
    print("   Verifique se a key está correta no .env")

print()
print("=" * 70)
print("✅ VERIFICAÇÃO CONCLUÍDA")
print("=" * 70)
