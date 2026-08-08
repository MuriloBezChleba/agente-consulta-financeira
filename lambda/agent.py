"""Agente que roteia a pergunta entre duas ferramentas — consulta estruturada (SQL) ou
busca em documentos de política (RAG) — e resume o resultado."""

import os

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from db import executar_select, validar_query_somente_leitura, QueryNotAllowedError
from rag import buscar_contexto

SCHEMA_DESCRICAO = """
Tabelas disponíveis (banco read-only):

clientes(id, nome, segmento)
ativos(id, cliente_id, categoria, valor, data_atualizacao)
transacoes(id, cliente_id, ativo_id, tipo, valor, data)

categoria em ativos: 'renda_fixa', 'renda_variavel', 'fundos_imobiliarios'
tipo em transacoes: 'compra', 'venda'
"""

PROMPT_ROTEADOR = ChatPromptTemplate.from_messages([
    ("system",
     "Classifique a pergunta do usuário em exatamente uma categoria:\n"
     "- 'dados' -> pergunta sobre números, valores, clientes, ativos ou transações específicas "
     "(precisa consultar um banco de dados).\n"
     "- 'politica' -> pergunta conceitual, normativa ou sobre regras/definições de produtos "
     "financeiros (precisa consultar documentação).\n"
     "Responda com APENAS uma palavra: dados ou politica."),
    ("human", "{pergunta}"),
])

PROMPT_SQL = ChatPromptTemplate.from_messages([
    ("system",
     "Você traduz perguntas em português para uma única query MySQL de LEITURA (SELECT). "
     "Nunca gere INSERT, UPDATE, DELETE ou qualquer comando de escrita. "
     "Responda APENAS com o SQL, sem explicação, sem markdown.\n\n"
     f"Schema:\n{SCHEMA_DESCRICAO}"),
    ("human", "{pergunta}"),
])

PROMPT_RESUMO_SQL = ChatPromptTemplate.from_messages([
    ("system",
     "Você resume o resultado de uma consulta financeira em uma frase clara, em português, "
     "para um analista de negócios. Não invente números que não estão no resultado."),
    ("human", "Pergunta original: {pergunta}\n\nResultado da query: {resultado}"),
])

PROMPT_RESUMO_RAG = ChatPromptTemplate.from_messages([
    ("system",
     "Você responde perguntas sobre política de investimento usando APENAS o contexto "
     "fornecido, em português, de forma clara. Se o contexto não tiver a resposta, diga que "
     "não encontrou essa informação nos documentos disponíveis."),
    ("human", "Pergunta: {pergunta}\n\nContexto (trechos de documentos):\n{contexto}"),
])


def _get_llm() -> ChatGroq:
    # console.groq.com — free tier bem mais folgado que o do NVIDIA NIM para chat.
    # Embeddings do RAG continuam via NVIDIA (ver rag.py) — Groq nao serve embeddings.
    return ChatGroq(
        model=os.environ.get("LLM_MODEL", "llama-3.1-8b-instant"),
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0,
        timeout=60,
    )


def classificar_pergunta(pergunta: str) -> str:
    """Roteamento do agente: decide qual ferramenta usar (dados x politica).

    Implementado como uma unica chamada de classificacao (nao tool-calling nativo do
    provedor) para manter previsibilidade e um numero minimo de chamadas de LLM por
    pergunta -- ver SPEC.md, secao 10, para a discussao dessa escolha.
    """
    llm = _get_llm()
    chain = PROMPT_ROTEADOR | llm | StrOutputParser()
    classe = chain.invoke({"pergunta": pergunta}).strip().lower()
    return "politica" if "politica" in classe else "dados"


def gerar_sql(pergunta: str) -> str:
    llm = _get_llm()
    chain = PROMPT_SQL | llm | StrOutputParser()
    sql = chain.invoke({"pergunta": pergunta}).strip()
    return sql.removeprefix("```sql").removesuffix("```").strip()


def resumir_resultado_sql(pergunta: str, resultado: list[dict]) -> str:
    if not resultado:
        return "Não foram encontrados dados para essa consulta."
    llm = _get_llm()
    chain = PROMPT_RESUMO_SQL | llm | StrOutputParser()
    return chain.invoke({"pergunta": pergunta, "resultado": str(resultado)})


def responder_com_dados(pergunta: str) -> dict:
    """Ferramenta 1: consulta estruturada. pergunta -> SQL -> guardrail -> execução -> resumo."""
    sql_gerado = gerar_sql(pergunta)

    try:
        validar_query_somente_leitura(sql_gerado)
    except QueryNotAllowedError as exc:
        return {
            "status": "bloqueado",
            "ferramenta": "sql",
            "erro": str(exc),
            "sql_gerado": sql_gerado,
            "resposta": None,
        }

    resultado = executar_select(sql_gerado)
    resumo = resumir_resultado_sql(pergunta, resultado)

    return {
        "status": "sucesso",
        "ferramenta": "sql",
        "sql_gerado": sql_gerado,
        "resposta": resumo,
    }


def responder_com_documentos(pergunta: str) -> dict:
    """Ferramenta 2: RAG sobre documentos de política de investimento."""
    contexto = buscar_contexto(pergunta)

    if not contexto:
        return {
            "status": "sucesso",
            "ferramenta": "rag",
            "sql_gerado": None,
            "resposta": "Não encontrei documentos relevantes para essa pergunta.",
        }

    llm = _get_llm()
    chain = PROMPT_RESUMO_RAG | llm | StrOutputParser()
    resposta = chain.invoke({"pergunta": pergunta, "contexto": contexto})

    return {
        "status": "sucesso",
        "ferramenta": "rag",
        "sql_gerado": None,
        "resposta": resposta,
    }


def responder_pergunta(pergunta: str) -> dict:
    """Orquestra o agente: roteia entre a ferramenta de dados (SQL) e a de documentos (RAG).

    Retorna um dict pronto para ser serializado na resposta da API, já contendo o que
    precisa ir para a auditoria (incluindo qual ferramenta foi usada).
    """
    ferramenta = classificar_pergunta(pergunta)

    if ferramenta == "politica":
        return responder_com_documentos(pergunta)
    return responder_com_dados(pergunta)
