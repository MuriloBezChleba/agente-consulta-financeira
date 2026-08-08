"""Agente que traduz pergunta em linguagem natural para SQL, executa e resume o resultado."""

import os

from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from db import executar_select, validar_query_somente_leitura, QueryNotAllowedError

SCHEMA_DESCRICAO = """
Tabelas disponíveis (banco read-only):

clientes(id, nome, segmento)
ativos(id, cliente_id, categoria, valor, data_atualizacao)
transacoes(id, cliente_id, ativo_id, tipo, valor, data)

categoria em ativos: 'renda_fixa', 'renda_variavel', 'fundos_imobiliarios'
tipo em transacoes: 'compra', 'venda'
"""

PROMPT_SQL = ChatPromptTemplate.from_messages([
    ("system",
     "Você traduz perguntas em português para uma única query MySQL de LEITURA (SELECT). "
     "Nunca gere INSERT, UPDATE, DELETE ou qualquer comando de escrita. "
     "Responda APENAS com o SQL, sem explicação, sem markdown.\n\n"
     f"Schema:\n{SCHEMA_DESCRICAO}"),
    ("human", "{pergunta}"),
])

PROMPT_RESUMO = ChatPromptTemplate.from_messages([
    ("system",
     "Você resume o resultado de uma consulta financeira em uma frase clara, em português, "
     "para um analista de negócios. Não invente números que não estão no resultado."),
    ("human", "Pergunta original: {pergunta}\n\nResultado da query: {resultado}"),
])


def _get_llm() -> ChatNVIDIA:
    # build.nvidia.com (NVIDIA NIM) — endpoint compativel, modelos hospedados na NVIDIA.
    return ChatNVIDIA(
        model=os.environ.get("LLM_MODEL", "meta/llama-3.1-8b-instruct"),
        api_key=os.environ["NVIDIA_API_KEY"],
        temperature=0,
        timeout=180,  # modelos 70B podem passar do timeout padrao de 60s, free tier as vezes oscila
    )


def gerar_sql(pergunta: str) -> str:
    llm = _get_llm()
    chain = PROMPT_SQL | llm | StrOutputParser()
    sql = chain.invoke({"pergunta": pergunta}).strip()
    return sql.removeprefix("```sql").removesuffix("```").strip()


def resumir_resultado(pergunta: str, resultado: list[dict]) -> str:
    if not resultado:
        return "Não foram encontrados dados para essa consulta."
    llm = _get_llm()
    chain = PROMPT_RESUMO | llm | StrOutputParser()
    return chain.invoke({"pergunta": pergunta, "resultado": str(resultado)})


def responder_pergunta(pergunta: str) -> dict:
    """Orquestra: pergunta -> SQL -> guardrail -> execução -> resumo.

    Retorna um dict pronto para ser serializado na resposta da API,
    já contendo o que precisa ir para a auditoria.
    """
    sql_gerado = gerar_sql(pergunta)

    try:
        validar_query_somente_leitura(sql_gerado)
    except QueryNotAllowedError as exc:
        return {
            "status": "bloqueado",
            "erro": str(exc),
            "sql_gerado": sql_gerado,
            "resposta": None,
        }

    resultado = executar_select(sql_gerado)
    resumo = resumir_resultado(pergunta, resultado)

    return {
        "status": "sucesso",
        "sql_gerado": sql_gerado,
        "resposta": resumo,
    }
