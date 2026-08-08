# SPEC — Agente de Consulta Financeira (Text-to-SQL com Orquestração de Agentes)

**Status:** Draft
**Versão:** 0.1.0faca nos
**Autor:** Murilo Bez Chleba
**Metodologia:** Spec-Driven Development (SDD)

---

## 1. Visão do Produto

### 1.1 Problema
Times de negócio (Asset Servicing, FP&A, Portfolio) gastam tempo consultando dados financeiros manualmente via SQL ou pedindo relatórios a analistas. Não há uma camada conversacional confiável, auditável e segura entre a pergunta em linguagem natural e o dado estruturado.

### 1.2 Solução
Um agente de IA que recebe perguntas em linguagem natural sobre dados financeiros (carteiras, ativos, transações), traduz para SQL, executa contra um banco relacional, e retorna resposta resumida — com trilha de auditoria completa e execução assíncrona para consultas pesadas.

### 1.3 É / Não É

| É | Não É |
|---|---|
| Agente de consulta (read-only) sobre dados financeiros | Sistema de execução de ordens/transações |
| Orquestração serverless (API Gateway → Lambda → SQS/SNS) | Aplicação monolítica sempre-ligada |
| Auditável e governado (log de toda consulta gerada) | Caixa-preta sem rastreabilidade |
| Ambiente local via LocalStack (dev) | Produção real com billing AWS (fora do escopo deste projeto pessoal) |

---

## 2. Personas

**Analista de Portfólio (Ana)** — precisa consultar posição de clientes sem escrever SQL.
**Auditor de Compliance (Caio)** — precisa revisar todo histórico de perguntas/respostas geradas pelo agente.

---

## 3. Requisitos Funcionais

| ID | Requisito | Prioridade |
|----|-----------|------------|
| RF01 | Sistema deve receber pergunta em linguagem natural via endpoint HTTP (API Gateway) | MUST |
| RF02 | Sistema deve traduzir a pergunta em uma query SQL válida e segura (somente `SELECT`) | MUST |
| RF03 | Sistema deve executar a query contra o banco MySQL e capturar o resultado | MUST |
| RF04 | Sistema deve resumir o resultado em linguagem natural via LLM | MUST |
| RF05 | Sistema deve registrar pergunta, SQL gerado, resultado e timestamp em tabela de auditoria | MUST |
| RF06 | Consultas marcadas como "relatório" devem ser processadas de forma assíncrona via fila (SQS) | SHOULD |
| RF07 | Conclusão de relatório assíncrono deve notificar via tópico (SNS) | SHOULD |
| RF08 | Sistema deve rejeitar queries geradas que contenham `INSERT`, `UPDATE`, `DELETE`, `DROP` (guardrail) | MUST |
| RF09 | Sistema deve permitir consulta do histórico de auditoria por período | COULD |

---

## 4. Requisitos Não-Funcionais

| ID | Requisito |
|----|-----------|
| RNF01 | **Segurança:** toda query gerada passa por validação de allowlist (somente `SELECT`) antes da execução |
| RNF02 | **Governança:** 100% das interações auditadas (pergunta, SQL, resultado, usuário, timestamp) |
| RNF03 | **Observabilidade:** logs estruturados em cada etapa (recepção, geração SQL, execução, resposta) |
| RNF04 | **Portabilidade:** código escrito contra o SDK real da AWS (boto3), compatível com deploy em produção sem reescrita |
| RNF05 | **Custo:** ambiente de desenvolvimento 100% local (LocalStack + Docker), zero custo de cloud |

---

## 5. Arquitetura (visão lógica)

```
Cliente (HTTP) 
   │
   ▼
API Gateway (LocalStack)
   │
   ▼
Lambda: handler.py  ──► agent.py (LangChain: NL → SQL)
   │                         │
   │                         ▼
   │                    db.py (MySQL)
   │
   ├── se "relatório pesado" ──► SQS (fila) ──► Lambda: sqs_worker.py ──► SNS (notificação)
   │
   ▼
Tabela de auditoria (MySQL): audit_log
```

---

## 6. Contrato de API

### `POST /query`

**Request:**
```json
{
  "pergunta": "Qual o total de ativos do cliente 123 em renda fixa?",
  "modo": "sincrono"
}
```

**Response 200:**
```json
{
  "resposta": "O cliente 123 possui R$ 452.300,00 em renda fixa, distribuídos em 4 ativos.",
  "sql_gerado": "SELECT SUM(valor) FROM ativos WHERE cliente_id = 123 AND categoria = 'renda_fixa'",
  "auditoria_id": "a1b2c3"
}
```

**Response 400 (guardrail acionado):**
```json
{
  "erro": "Query gerada contém operação não permitida (somente SELECT é aceito)."
}
```

### `POST /query` (modo assíncrono)

**Request:**
```json
{ "pergunta": "Gere relatório completo de exposição por classe de ativo", "modo": "assincrono" }
```

**Response 202:**
```json
{ "status": "processando", "job_id": "job-789" }
```

---

## 7. Modelo de Dados (resumo)

```sql
clientes(id, nome, segmento)
ativos(id, cliente_id, categoria, valor, data_atualizacao)
transacoes(id, cliente_id, ativo_id, tipo, valor, data)
audit_log(id, pergunta, sql_gerado, resultado_resumo, usuario, timestamp, status)
```

Schema completo em `db/schema.sql`.

---

## 8. Critérios de Aceite

- [ ] Pergunta válida retorna resposta correta em < 5s (modo síncrono, ambiente local)
- [ ] Query com tentativa de escrita (`DELETE`, `UPDATE` etc.) é bloqueada e logada como tentativa
- [ ] Toda interação aparece na tabela `audit_log` sem exceção
- [ ] Modo assíncrono retorna `job_id` imediatamente e processa via SQS sem bloquear o cliente
- [ ] Testes unitários cobrem: geração de SQL, guardrail de segurança, parsing de resposta

---

## 9. Fora de Escopo (v0.1)

- Autenticação/autorização de usuários (fica para v0.2)
- Multi-tenancy real
- Deploy em conta AWS real (billing)
- Suporte a múltiplos bancos de dados simultâneos

---

## 10. Perguntas em Aberto

- Qual LLM usar para geração de SQL: OpenAI, Bedrock (Claude/Titan) ou Vertex AI? → decidir na fase de implementação, testar qual gera SQL mais confiável para o schema.
- Vale adicionar reranking/validação de SQL via segundo LLM (self-check) antes de executar?
