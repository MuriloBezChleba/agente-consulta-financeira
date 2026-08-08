"""CLI interativa para testar o agente sem precisar do LocalStack/API Gateway.

Uso:
    python cli.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lambda"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
os.environ.setdefault("DB_HOST", "localhost")

from agent import responder_pergunta
from db import registrar_auditoria

BANNER = """
Agente de Consulta Financeira — CLI
Digite sua pergunta (dados de clientes/ativos ou politica de investimento).
Comandos: 'sair' ou Ctrl+C para encerrar.
"""


def main():
    print(BANNER)

    while True:
        try:
            pergunta = input("Pergunta> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAte mais.")
            break

        if not pergunta:
            continue
        if pergunta.lower() in ("sair", "exit", "quit"):
            print("Ate mais.")
            break

        try:
            resultado = responder_pergunta(pergunta)
        except Exception as exc:
            print(f"[erro] {exc}\n")
            continue

        auditoria_id = registrar_auditoria(
            pergunta=pergunta,
            sql_gerado=resultado.get("sql_gerado"),
            resultado_resumo=resultado.get("resposta") or resultado.get("erro"),
            status=resultado["status"],
            ferramenta=resultado.get("ferramenta", "sql"),
        )

        print(f"[ferramenta: {resultado.get('ferramenta', '?')}]")
        if resultado.get("sql_gerado"):
            print(f"[sql: {resultado['sql_gerado']}]")

        if resultado["status"] == "bloqueado":
            print(f"BLOQUEADO: {resultado['erro']}")
        else:
            print(resultado["resposta"])

        print(f"[auditoria: {auditoria_id}]\n")


if __name__ == "__main__":
    main()
