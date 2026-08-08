"""Servidor MCP (Model Context Protocol) que expõe o agente de consulta financeira
como duas ferramentas padrão, utilizáveis por qualquer cliente MCP (Claude Desktop,
outros agentes, etc.) — mesma lógica de negócio usada pelo handler Lambda/API
Gateway, apenas com uma interface de transporte diferente.

Diferente do endpoint HTTP (que roteia internamente via LLM), aqui cada ferramenta
é exposta separadamente: quem decide qual usar é o cliente MCP (outro agente/LLM),
com base na descrição de cada tool -- um padrão mais próximo de "orquestração de
múltiplos agentes/ferramentas" do que um único ponto de entrada com roteador oculto.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lambda"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from fastmcp import FastMCP

from agent import responder_com_dados, responder_com_documentos
from db import registrar_auditoria

mcp = FastMCP("Agente de Consulta Financeira")


def _auditar_e_formatar(pergunta: str, resultado: dict) -> str:
    registrar_auditoria(
        pergunta=pergunta,
        sql_gerado=resultado.get("sql_gerado"),
        resultado_resumo=resultado.get("resposta") or resultado.get("erro"),
        status=resultado["status"],
        ferramenta=resultado.get("ferramenta", "sql"),
    )

    if resultado["status"] == "bloqueado":
        return f"Consulta bloqueada por segurança: {resultado['erro']}"

    return resultado["resposta"]


@mcp.tool()
def consultar_dados_financeiros(pergunta: str) -> str:
    """Consulta dados financeiros estruturados: clientes, ativos e transações
    específicas (valores, quantidades, categorias, datas). Traduz a pergunta para
    SQL de LEITURA (somente SELECT, com guardrail de segurança) e executa contra o
    banco. Use para perguntas sobre números e registros concretos -- ex.: "quanto o
    cliente 5 tem em renda variável", "quantas transações de compra houve em julho".
    """
    resultado = responder_com_dados(pergunta)
    return _auditar_e_formatar(pergunta, resultado)


@mcp.tool()
def consultar_politica_investimento(pergunta: str) -> str:
    """Consulta a documentação de política de investimento (regras de alocação,
    liquidez, tributação) para renda fixa, renda variável e fundos imobiliários (FII)
    via busca vetorial (RAG). Use para perguntas conceituais/normativas -- ex.: "qual
    o limite de alocação em FIIs", "qual a liquidez de renda variável".
    """
    resultado = responder_com_documentos(pergunta)
    return _auditar_e_formatar(pergunta, resultado)


if __name__ == "__main__":
    mcp.run()
