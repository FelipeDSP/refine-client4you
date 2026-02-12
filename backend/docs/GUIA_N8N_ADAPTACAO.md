# 🤖 Guia de Adaptação do Workflow n8n para Client4You

## 📋 Resumo

Este guia explica como adaptar seu workflow existente do n8n (que usa WAHA Trigger) para funcionar com o Client4You.

---

## 🔄 O que Mudou?

| Antes (WAHA Trigger) | Agora (Webhook HTTP) |
|---------------------|---------------------|
| WAHA envia diretamente para n8n | Backend Client4You recebe primeiro |
| Não tem contexto da empresa | Inclui dados da empresa e agente |
| Precisa buscar configs separado | Tudo vem no payload |

---

## 📦 Payload que o Client4You Envia

```json
{
  // === COMPATÍVEL COM WAHA TRIGGER ===
  "payload": {
    "from": "5511999999999@c.us",
    "body": "Olá, preciso de ajuda",
    "fromMe": false,
    "_data": {
      "notifyName": "João Silva",
      "Message": {
        "conversation": "Olá, preciso de ajuda"
      }
    }
  },
  
  // === DADOS EXTRAÍDOS ===
  "telefone_normalizado": "5511999999999",
  "texto_cliente": "Olá, preciso de ajuda",
  
  // === VARIÁVEIS PRONTAS PARA USAR ===
  "variaveis": {
    "server_url": "https://waha.suaempresa.com",
    "instancia": "nome_da_sessao",
    "api_key": "sua-api-key",
    "phone": "5511999999999",
    "mensagem": "Olá, preciso de ajuda"
  },
  
  // === CONTEXTO DO CLIENT4YOU ===
  "client4you": {
    "company_id": "uuid-da-empresa",
    "company_name": "Empresa XYZ",
    "session_name": "empresa_xyz_abc123",
    "agent_config": {
      "name": "Carol",
      "personality": "acolhedora e profissional",
      "system_prompt": "Você é a Carol, assistente...",
      "model": "gpt-4.1-mini",
      "temperature": 0.7
    }
  },
  
  // === TIPO DE MENSAGEM ===
  "message_type": "text",  // ou "audio"
  "has_media": false,
  "media_url": null
}
```

---

## 🛠️ Como Adaptar seu Workflow

### Passo 1: Substituir o WAHA Trigger por Webhook

1. Adicione um node **Webhook** no n8n
2. Configure como `POST`
3. Anote a URL gerada (ex: `https://seu-n8n.com/webhook/abc123`)
4. Configure no backend: `N8N_WEBHOOK_URL=https://seu-n8n.com/webhook/abc123`

### Passo 2: Atualizar os Nodes que Extraem Dados

**Antes (node "Extrair Telefone"):**
```javascript
let rawNumber = payload.from || payload._data?.Info?.Chat || "";
```

**Depois (já vem pronto):**
```javascript
// O telefone já vem extraído no payload
let rawNumber = $json.telefone_normalizado;
let texto = $json.texto_cliente;
```

### Passo 3: Atualizar o Node "Variaveis"

**Antes:**
```javascript
{
  "server_url": "https://waha.chatyou.chat",  // HARDCODED
  "instancia": "romiltoprospeccao",           // HARDCODED
  "api_key": "chave-fixa",                    // HARDCODED
  "phone": "{{ extrai do telefone }}",
  "mensagem": "{{ extrai da mensagem }}"
}
```

**Depois (usa o que vem no payload):**
```javascript
{
  "server_url": "={{ $json.variaveis.server_url }}",
  "instancia": "={{ $json.variaveis.instancia }}",
  "api_key": "={{ $json.variaveis.api_key }}",
  "phone": "={{ $json.variaveis.phone }}",
  "mensagem": "={{ $json.variaveis.mensagem }}"
}
```

### Passo 4: Usar o Prompt Dinâmico do Cliente

**Antes (prompt fixo):**
```javascript
"Você é a Carol, assistente virtual do time do Psicólogo Romilto Lopes..."
```

**Depois (usa config do cliente):**
```javascript
// No node "Prompt", use:
"={{ $json.client4you.agent_config.system_prompt }}"

// Ou combine com personalidade:
`${$json.client4you.agent_config.system_prompt}

Personalidade: ${$json.client4you.agent_config.personality}
Nome do assistente: ${$json.client4you.agent_config.name}`
```

### Passo 5: Atualizar Tabela do Supabase (Debounce/Status)

O workflow atual usa a tabela `Romilto_LeadsProspectaIA`. Para funcionar multi-tenant:

**Opção A: Uma tabela por cliente**
- Criar tabelas dinâmicas: `{company_id}_leads_ia`

**Opção B: Tabela única com company_id (RECOMENDADO)**
- Adicionar coluna `company_id` na tabela
- Filtrar sempre por `company_id`

```javascript
// Exemplo de filtro no Supabase node:
{
  "keyName": "telefone",
  "keyValue": "={{ $json.telefone_normalizado }}"
},
{
  "keyName": "company_id",
  "keyValue": "={{ $json.client4you.company_id }}"
}
```

---

## 🏗️ Estrutura Sugerida do Workflow Adaptado

```
[Webhook HTTP]
      │
      ▼
[Edit Fields] ─── Extrai dados do payload
      │
      ▼
[Supabase: Get] ─── Busca lead com company_id
      │
      ▼
[IF: Status Ativo?]
      │
      ├── SIM ──► [Debounce com Redis]
      │                    │
      │                    ▼
      │           [AI Agent com prompt dinâmico]
      │                    │
      │                    ▼
      │           [HTTP: Envia WhatsApp via WAHA]
      │
      └── NÃO ──► [No Operation]
```

---

## ⚙️ Variáveis de Ambiente Necessárias

No backend do Client4You:

```bash
# URL do webhook do n8n (obrigatório para agente IA)
N8N_WEBHOOK_URL=https://seu-n8n.com/webhook/seu-webhook-id

# WAHA padrão (usado se empresa não tiver config específica)
WAHA_DEFAULT_URL=https://waha.seudominio.com
WAHA_MASTER_KEY=sua-master-key
```

---

## 📊 Tabela de Configuração do Agente (Supabase)

```sql
CREATE TABLE agent_configs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID REFERENCES companies(id),
  enabled BOOLEAN DEFAULT false,
  name VARCHAR(100) DEFAULT 'Assistente',
  personality TEXT,
  system_prompt TEXT,
  model VARCHAR(50) DEFAULT 'gpt-4.1-mini',
  temperature DECIMAL(2,1) DEFAULT 0.7,
  response_delay INTEGER DEFAULT 3,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 🧪 Testando a Integração

1. Configure `N8N_WEBHOOK_URL` no backend
2. Ative o agente para uma empresa no painel
3. Envie uma mensagem para o WhatsApp da empresa
4. Verifique os logs do n8n

---

## 🆘 Problemas Comuns

| Problema | Solução |
|----------|---------|
| n8n não recebe | Verificar `N8N_WEBHOOK_URL` está correta |
| Resposta não enviada | Verificar `variaveis.server_url` e `variaveis.api_key` |
| Mensagem duplicada | Implementar debounce corretamente |
| Erro no Supabase | Adicionar `company_id` nos filtros |

---

## 📞 Suporte

Se precisar de ajuda para adaptar seu workflow, entre em contato!
