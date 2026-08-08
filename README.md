# Agente de Consulta Financeira

Agente de IA que roteia perguntas em linguagem natural entre duas ferramentas — consulta estruturada (texto → SQL → MySQL) ou busca em documentos de política de investimento (RAG, FAISS) — e retorna uma resposta resumida. Guardrails de segurança, auditoria completa, processamento assíncrono para relatórios pesados, e uma interface adicional via **MCP (Model Context Protocol)** para uso por outros agentes/clientes.

Arquitetura orientada a eventos rodando sobre a API real da AWS (API Gateway, Lambda, SQS, SNS), emulada localmente via [LocalStack](https://localstack.cloud) — sem custo de nuvem, com código 100% portável para uma conta AWS real.

> Este é um projeto pessoal de estudo/portfólio. Todos os dados financeiros usados são sintéticos.

## Por que este projeto existe

Construí isso pra aplicar, na prática, um fluxo real de agente de IA orientado a especificação (Spec-Driven Development): comecei pelo [`SPEC.md`](./SPEC.md) — requisitos funcionais, não-funcionais, contrato de API, modelo de dados e critérios de aceite — antes de escrever qualquer código.

## Arquitetura

```
Cliente (HTTP)                    Cliente MCP (Claude Desktop, outro agente...)
   │                                          │
   ▼                                          ▼
API Gateway (LocalStack)              mcp_server/server.py (FastMCP)
   │                                          │
   ▼                                          │
Lambda: handler.py ───────────┐               │
   │                          │               │
   │                          ▼               ▼
   │                agent.py — roteador (LLM decide: dados x politica)
   │                          │
   │              ┌───────────┴───────────┐
   │              ▼                       ▼
   │     Ferramenta SQL            Ferramenta RAG
   │     (NL → SQL → guardrail     (embeddings → FAISS →
   │      → db.py → MySQL)          contexto → resumo)
   │              │                       │
   │              └───────────┬───────────┘
   │                          ▼
   │              audit_log (MySQL) — pergunta, ferramenta usada, resultado
   │
   ├── modo "assincrono" ──► SQS ──► Lambda: sqs_worker.py ──► SNS (notificação)
```

Chat (roteador, geração de SQL, resumos): **Groq**. Embeddings do RAG: **NVIDIA NIM**
(build.nvidia.com) — dois provedores porque Groq não oferece embeddings; ver [`SPEC.md`](./SPEC.md#10-perguntas-em-aberto) para o porquê dessa escolha.

## Guardrails de segurança

- O agente só tem permissão de **leitura**: qualquer SQL gerado que não comece com `SELECT`, ou contenha `INSERT`/`UPDATE`/`DELETE`/`DROP`/etc., é bloqueado antes de chegar ao banco (ver `db.py::validar_query_somente_leitura`).
- Toda interação — sucesso, bloqueio ou erro — é gravada em `audit_log`.

## Stack

Python · LangChain · Groq (chat) · NVIDIA NIM (embeddings) · FAISS (RAG) · MCP/FastMCP · MySQL · AWS (API Gateway, Lambda, SQS, SNS) via LocalStack · Docker

## Como rodar localmente

Pré-requisitos: Docker, Python 3.12+, [AWS CLI v2](https://aws.amazon.com/cli/).

```bash
# 1. Configurar variáveis de ambiente
cp .env.example .env
# edite o .env com NVIDIA_API_KEY (gratuita em build.nvidia.com, so para embeddings),
# GROQ_API_KEY (gratuita em console.groq.com, para chat) e uma senha de banco local

# 2. Subir LocalStack + MySQL
docker compose up -d

# 3. Instalar dependências
pip install -r lambda/requirements.txt

# 4. Criar os recursos AWS (API Gateway, Lambda, SQS, SNS) no LocalStack
export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1
bash infra/setup_aws.sh

# 5. Rodar os testes
pytest tests/
```

## Uso via CLI

Forma mais rápida de testar o agente sem passar pelo LocalStack/API Gateway (precisa só do
MySQL rodando):

```bash
docker compose up -d mysql
python cli.py
```

```
Pergunta> Qual o total de ativos do cliente 1 em renda fixa?
[ferramenta: sql]
[sql: SELECT COUNT(*) FROM ativos WHERE cliente_id = 1 AND categoria = 'renda_fixa']
O cliente 1 tem 1 ativo em renda fixa.
[auditoria: ac4fa265-...]

Pergunta> Qual o limite de alocacao em fundos imobiliarios recomendado?
[ferramenta: rag]
Recomenda-se concentração máxima de 25% do patrimônio em FIIs por cliente...
[auditoria: 8b554d18-...]
```

## Uso via MCP

Além da API HTTP, o agente pode ser usado como uma ferramenta MCP padrão — útil para
conectar a Claude Desktop ou a outro agente que fale o protocolo:

```bash
pip install -r mcp_server/requirements.txt
python mcp_server/server.py
```

Isso expõe a tool `perguntar_financeiro(pergunta)`, que roda a mesma lógica de negócio
(`agent.responder_pergunta`) usada pelo handler HTTP, incluindo guardrail e auditoria.

### Solução de problemas conhecidos

- **LocalStack pedindo `LOCALSTACK_AUTH_TOKEN` mesmo em serviços gratuitos**: a tag `latest` mudou de comportamento. Este projeto já fixa a imagem em `localstack/localstack:3.8.1` no `docker-compose.yml`, que roda 100% community sem token.
- **`awslocal` com segmentation fault (Windows/Git Bash)**: em vez do wrapper, use o `aws` CLI real com `--endpoint-url=http://localhost:4566` e credenciais fake (`AWS_ACCESS_KEY_ID=test`) — é o que `infra/setup_aws.sh` assume.
- **Lambda travando com `exec format error` / `fork/exec /var/runtime/bootstrap`**: sintoma de um bug de emulação do executor Docker-in-Docker do LocalStack em alguns setups de Docker Desktop + WSL2, mesmo com imagem `amd64` nativa confirmada. Contorno usado para validar a lógica de ponta a ponta: invocar `handler.lambda_handler(event, None)` diretamente em um processo Python local (apontando `DB_HOST=localhost` e `AWS_ENDPOINT_URL=http://localhost:4566`), sem passar pelo executor de container da Lambda. O código do handler é idêntico ao que rodaria dentro do container.

## Estrutura do projeto

```
├── SPEC.md                    # especificação completa (Spec-Driven Development)
├── cli.py                      # CLI interativa para testar o agente localmente
├── docker-compose.yml          # LocalStack + MySQL
├── infra/setup_aws.sh          # provisiona os recursos AWS no LocalStack
├── lambda/
│   ├── handler.py               # entrypoint API Gateway
│   ├── agent.py                  # roteador do agente (dados x politica) + resumos
│   ├── rag.py                     # busca vetorial (FAISS) sobre documentos de política
│   ├── db.py                       # acesso ao MySQL + guardrail de segurança
│   └── sqs_worker.py                # processamento assíncrono de relatórios
├── mcp_server/
│   └── server.py                     # expõe o agente como ferramenta MCP (FastMCP)
├── db/
│   ├── schema.sql                     # schema + dados sintéticos
│   └── documentos/                     # fonte do RAG (políticas de investimento sintéticas)
└── tests/                               # testes unitários
```

## Status

Fluxo completo validado localmente de ponta a ponta nas duas ferramentas: consulta estruturada (pergunta → SQL → MySQL → resumo) e RAG (pergunta → busca vetorial → contexto → resumo), com roteamento automático entre as duas e registro em auditoria. Servidor MCP validado (importação e registro da tool). Próximos passos documentados em [`SPEC.md`](./SPEC.md#10-perguntas-em-aberto).

## Autor

Murilo Bez Chleba — [LinkedIn](https://www.linkedin.com/in/murilo-gonzalez-bez-chleba/) · [GitHub](https://github.com/MuriloBezChleba)
