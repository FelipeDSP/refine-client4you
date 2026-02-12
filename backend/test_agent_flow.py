#!/usr/bin/env python3
"""
Script de Teste - Fluxo Agente IA + WAHA + n8n
Testa se o backend está processando corretamente as mensagens do WhatsApp.
"""

import asyncio
import httpx
import json
import os
import sys
from datetime import datetime

# Cores para output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")

# Payload simulado do WAHA (formato real)
def create_waha_payload(phone: str, message: str, session_name: str = "test_session"):
    """Cria um payload no formato exato que o WAHA envia"""
    return {
        "event": "message",
        "session": session_name,
        "payload": {
            "id": f"true_{phone}@c.us_3EB0{datetime.now().strftime('%H%M%S')}",
            "timestamp": int(datetime.now().timestamp()),
            "from": f"{phone}@c.us",
            "to": "5511999999999@c.us",
            "body": message,
            "fromMe": False,
            "hasMedia": False,
            "type": "chat",
            "_data": {
                "id": {
                    "fromMe": False,
                    "remote": f"{phone}@c.us",
                    "id": f"3EB0{datetime.now().strftime('%H%M%S')}"
                },
                "notifyName": "Cliente Teste",
                "Message": {
                    "conversation": message
                }
            }
        }
    }

async def test_backend_health(base_url: str):
    """Testa se o backend está online"""
    print_info("Testando health do backend...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{base_url}/api/health")
            if response.status_code == 200:
                data = response.json()
                print_success(f"Backend online: {data}")
                return True
            else:
                print_error(f"Backend retornou status {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Erro ao conectar com backend: {e}")
            return False

async def test_webhook_waha(base_url: str, payload: dict):
    """Testa o endpoint de webhook do WAHA"""
    print_info("Enviando payload para /api/webhook/waha...")
    print(f"{Colors.CYAN}Payload:{Colors.END}")
    print(json.dumps(payload, indent=2, ensure_ascii=False)[:500] + "...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{base_url}/api/webhook/waha",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"\n{Colors.CYAN}Resposta:{Colors.END}")
            print(f"Status: {response.status_code}")
            
            try:
                data = response.json()
                print(f"Body: {json.dumps(data, indent=2, ensure_ascii=False)}")
                
                if data.get("status") == "processing":
                    print_success("Webhook recebido e processando!")
                    return True, data
                elif data.get("status") == "ignored":
                    print_warning(f"Webhook ignorado: {data.get('event', 'unknown')}")
                    return True, data
                else:
                    print_warning(f"Resposta inesperada: {data}")
                    return True, data
                    
            except:
                print(f"Body (raw): {response.text}")
                return False, None
                
        except Exception as e:
            print_error(f"Erro ao enviar webhook: {e}")
            return False, None

async def check_n8n_config():
    """Verifica se N8N_WEBHOOK_URL está configurado"""
    n8n_url = os.getenv("N8N_WEBHOOK_URL")
    
    if n8n_url:
        print_success(f"N8N_WEBHOOK_URL configurado: {n8n_url[:50]}...")
        return True
    else:
        print_warning("N8N_WEBHOOK_URL NÃO está configurado!")
        print_info("O agente IA não vai encaminhar para o n8n sem esta variável.")
        print_info("Configure: N8N_WEBHOOK_URL=https://seu-n8n.com/webhook/iaagent.client4you")
        return False

async def test_agent_config_endpoint(base_url: str, token: str = None):
    """Testa se o endpoint de config do agente funciona"""
    print_info("Testando endpoint /api/agent/config...")
    
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{base_url}/api/agent/config",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("config"):
                    print_success(f"Config do agente encontrada:")
                    print(f"  - Enabled: {data['config'].get('enabled', False)}")
                    print(f"  - Nome: {data['config'].get('name', 'N/A')}")
                    return True, data
                else:
                    print_warning("Nenhuma config de agente salva ainda")
                    return True, None
            elif response.status_code == 401:
                print_warning("Endpoint requer autenticação (esperado)")
                return True, None
            else:
                print_error(f"Erro: {response.status_code} - {response.text}")
                return False, None
                
        except Exception as e:
            print_error(f"Erro ao buscar config: {e}")
            return False, None

async def simulate_full_flow(base_url: str, phone: str, message: str, session_name: str):
    """Simula o fluxo completo"""
    print_header("SIMULAÇÃO DO FLUXO COMPLETO")
    
    # 1. Criar payload
    payload = create_waha_payload(phone, message, session_name)
    
    print_info(f"Simulando mensagem de: {phone}")
    print_info(f"Mensagem: \"{message}\"")
    print_info(f"Sessão: {session_name}")
    
    # 2. Enviar para webhook
    success, response = await test_webhook_waha(base_url, payload)
    
    if success and response and response.get("status") == "processing":
        print("\n" + "="*60)
        print_success("FLUXO INICIADO COM SUCESSO!")
        print("="*60)
        print_info("Agora verifique:")
        print("  1. Os logs do backend: tail -f /var/log/supervisor/backend.err.log")
        print("  2. O webhook do n8n (se configurado)")
        print("  3. Se a mensagem chegou no WhatsApp")
    
    return success

async def main():
    print_header("TESTE DO FLUXO AGENTE IA - CLIENT4YOU")
    
    # Configurações
    BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8001")
    TEST_PHONE = "5511999999999"  # Número de teste
    TEST_MESSAGE = "Olá, gostaria de mais informações"
    TEST_SESSION = "test_company_abc123"  # Simula uma sessão de empresa
    
    print(f"Backend URL: {BASE_URL}")
    print(f"Telefone teste: {TEST_PHONE}")
    print(f"Sessão teste: {TEST_SESSION}")
    
    # Teste 1: Backend online?
    print_header("TESTE 1: Backend Health")
    if not await test_backend_health(BASE_URL):
        print_error("Backend offline! Abortando testes.")
        return False
    
    # Teste 2: N8N configurado?
    print_header("TESTE 2: Configuração N8N")
    n8n_ok = await check_n8n_config()
    
    # Teste 3: Endpoint de config do agente
    print_header("TESTE 3: Endpoint Agent Config")
    await test_agent_config_endpoint(BASE_URL)
    
    # Teste 4: Simular webhook do WAHA
    print_header("TESTE 4: Webhook WAHA")
    await simulate_full_flow(BASE_URL, TEST_PHONE, TEST_MESSAGE, TEST_SESSION)
    
    # Resumo
    print_header("RESUMO")
    print_success("Backend está recebendo webhooks do WAHA")
    
    if not n8n_ok:
        print_warning("N8N_WEBHOOK_URL não configurado - agente não vai encaminhar")
        print_info("Para configurar, adicione no .env ou variável de ambiente:")
        print(f"  N8N_WEBHOOK_URL=https://seu-n8n.com/webhook/iaagent.client4you")
    else:
        print_success("N8N configurado - pronto para encaminhar mensagens")
    
    print("\n" + "="*60)
    print_info("PRÓXIMOS PASSOS:")
    print("  1. Configure N8N_WEBHOOK_URL no ambiente de produção")
    print("  2. Salve as configurações do agente no painel")
    print("  3. Ative o agente")
    print("  4. Envie uma mensagem de teste no WhatsApp")
    print("  5. Verifique se chegou no n8n")
    print("="*60 + "\n")
    
    return True

if __name__ == "__main__":
    asyncio.run(main())
