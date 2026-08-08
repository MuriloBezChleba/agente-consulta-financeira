# Agente de Consulta Financeira

Agente de IA que traduz perguntas em linguagem natural para SQL, consulta uma base financeira (MySQL) e retorna uma resposta resumida — com guardrails de segurança, auditoria completa e processamento assíncrono para relatórios pesados.

Arquitetura orientada a eventos rodando sobre a API real da AWS (API Gateway, Lambda, SQS, SNS), emulada localmente via [LocalStack](https://localstack.cloud) — sem custo de nuvem, com código 100% portável para uma conta AWS real.

> Este é um projeto pessoal de estudo/portfólio. Todos os dados financeiros usados são sintéticos.

## Por que este projeto existe

Construí isso pra aplicar, na prática, um fluxo real de agente de IA orientado a especificação (Spec-Driven Development): comecei pelo [`SPEC.md`](./SPEC.md) — requisitos funcionais, não-funcionais, contrato de API, modelo de dados e critérios de aceite — antes de escrever qualquer código.

## Arquitetura

```
Cliente (HTTP)
   │
   ▼
API Gateway (LocalStack)
   │
   ▼
Lambda: handler.py ──► agent.py (LangChain: linguagem natural → SQL)
   │                         │
   │                         ▼
   │                    db.py (MySQL, somente leitura)
   │
   ├── modo "assincrono" ──► SQS ──► Lambda: sqs_worker.py ──► SNS (notificação)
   │
   ▼
audit_log (MySQL) — toda pergunta, SQL gerado e resultado ficam registrados
```

## Guardrails de segurança

- O agente só tem permissão de **leitura**: qualquer SQL gerado que não comece com `SELECT`, ou contenha `INSERT`/`UPDATE`/`DELETE`/`DROP`/etc., é bloqueado antes de chegar ao banco (ver `db.py::validar_query_somente_leitura`).
- Toda interação — sucesso, bloqueio ou erro — é gravada em `audit_log`.

## Stack

Python · LangChain · MySQL · AWS (API Gateway, Lambda, SQS, SNS) via LocalStack · Docker

## Como rodar localmente

Pré-requisitos: Docker, Python 3.12+, [`awscli-local`](https://github.com/localstack/awscli-local).

```bash
# 1. Configurar variáveis de ambiente
cp .env.example .env
# edite o .env com sua OPENAI_API_KEY e uma senha de banco local

# 2. Subir LocalStack + MySQL
docker-compose up -d

# 3. Instalar dependências
pip install -r lambda/requirements.txt

# 4. Criar os recursos AWS (API Gateway, Lambda, SQS, SNS) no LocalStack
bash infra/setup_aws.sh

# 5. Rodar os testes
pytest tests/
```

## Estrutura do projeto

```
├── SPEC.md              # especificação completa (Spec-Driven Development)
├── docker-compose.yml    # LocalStack + MySQL
├── infra/setup_aws.sh    # provisiona os recursos AWS no LocalStack
├── lambda/
│   ├── handler.py        # entrypoint API Gateway
│   ├── agent.py           # orquestração do agente (NL → SQL → resposta)
│   ├── db.py               # acesso ao MySQL + guardrail de segurança
│   └── sqs_worker.py       # processamento assíncrono de relatórios
├── db/schema.sql          # schema + dados sintéticos
└── tests/                 # testes unitários
```

## Status

Projeto em desenvolvimento ativo — próximos passos documentados em [`SPEC.md`](./SPEC.md#10-perguntas-em-aberto).

## Autor

Murilo Bez Chleba — [LinkedIn](https://www.linkedin.com/in/murilo-gonzalez-bez-chleba/) · [GitHub](https://github.com/MuriloBezChleba)
