"""Servidor MCP (Model Context Protocol) que expõe o agente de consulta financeira
como uma ferramenta padrão, utilizável por qualquer cliente MCP (Claude Desktop,
outros agentes, etc.) — mesma lógica de negócio usada pelo handler Lambda/API
Gateway, apenas com uma interface de transporte diferente.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lambda"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from fastmcp import FastMCP

from agent import responder_pergunta
from db import registrar_auditoria

mcp = FastMCP("Agente de Consulta Financeira")


@mcp.tool()
def perguntar_financeiro(pergunta: str) -> str:
    """Responde perguntas sobre dados financeiros (clientes, ativos, transações) ou sobre
    política de investimento (renda fixa, renda variável, fundos imobiliários), roteando
    automaticamente entre consulta ao banco (SQL, somente leitura) e busca em documentos
    (RAG). Toda interação fica registrada em auditoria.
    """
    resultado = responder_pergunta(pergunta)

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


if __name__ == "__main__":
    mcp.run()
