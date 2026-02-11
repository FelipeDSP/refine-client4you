#!/usr/bin/env python3
"""
Script para testar o envio de emails
"""
import sys
import asyncio
sys.path.append('/app/backend')

from email_service import get_email_service
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')

async def test_email():
    print("=" * 70)
    print("🧪 TESTE DE ENVIO DE EMAIL")
    print("=" * 70)
    print()
    
    email_service = get_email_service()
    
    # Email de teste
    test_email = input("Digite seu email para teste: ").strip()
    
    if not test_email:
        print("❌ Email não fornecido")
        return
    
    print()
    print("📧 Enviando email de teste...")
    print()
    
    # Teste 1: Email simples
    success = await email_service.send_email(
        to_email=test_email,
        subject="🧪 Teste de Email - Client4You",
        html_body="""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #FF8C00;">✅ Teste de Email Funcionando!</h2>
            <p>Este é um email de teste do sistema Client4You.</p>
            <p>Se você recebeu este email, significa que a configuração SMTP está correta! 🎉</p>
            <hr>
            <p style="color: #666; font-size: 12px;">Client4You - Sistema de Gestão de Leads</p>
        </body>
        </html>
        """,
        plain_body="Teste de email - Client4You\n\nSe você recebeu este email, a configuração SMTP está correta!"
    )
    
    if success:
        print("✅ Email de teste enviado com sucesso!")
        print(f"   Verifique a caixa de entrada de: {test_email}")
    else:
        print("❌ Falha ao enviar email de teste")
        print("   Verifique as configurações SMTP no .env")
    
    print()
    
    # Teste 2: Email de compra (se o primeiro funcionar)
    if success:
        print("=" * 70)
        print("🧪 TESTE 2: EMAIL DE CONFIRMAÇÃO DE COMPRA")
        print("=" * 70)
        print()
        
        success2 = await email_service.send_purchase_confirmation(
            user_email=test_email,
            user_name="Usuário Teste",
            plan_name="Plano Intermediário",
            plan_features=[
                "Buscas de leads ilimitadas",
                "Disparador WhatsApp ilimitado",
                "Suporte prioritário"
            ],
            order_id="TEST-12345"
        )
        
        if success2:
            print("✅ Email de confirmação de compra enviado!")
        else:
            print("❌ Falha ao enviar email de confirmação")
    
    print()
    print("=" * 70)
    print("✅ TESTES CONCLUÍDOS")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_email())
