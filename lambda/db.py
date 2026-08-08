"""Camada de acesso ao MySQL. Apenas leitura (SELECT) é permitida por design."""

import os
import uuid
from datetime import datetime

import mysql.connector
from mysql.connector import Error

# Palavras que nunca podem aparecer numa query gerada pelo agente.
# Guardrail de segurança: o agente só tem permissão de leitura.
FORBIDDEN_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
    "TRUNCATE", "CREATE", "GRANT", "REVOKE", "REPLACE",
)


class QueryNotAllowedError(Exception):
    """Levantada quando o SQL gerado pelo agente tenta uma operação de escrita."""


def _get_connection():
    return mysql.connector.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", 3306)),
        database=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )


def validar_query_somente_leitura(sql: str) -> None:
    normalizado = sql.strip().upper()
    if not normalizado.startswith("SELECT"):
        raise QueryNotAllowedError("Apenas queries SELECT são permitidas.")
    if any(palavra in normalizado for palavra in FORBIDDEN_KEYWORDS):
        raise QueryNotAllowedError("Query contém operação de escrita não permitida.")


def executar_select(sql: str) -> list[dict]:
    validar_query_somente_leitura(sql)

    conn = _get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql)
        resultado = cursor.fetchall()
        cursor.close()
        return resultado
    except Error as exc:
        raise RuntimeError(f"Erro ao executar query: {exc}") from exc
    finally:
        conn.close()


def registrar_auditoria(
    pergunta: str,
    sql_gerado: str | None,
    resultado_resumo: str | None,
    status: str,
    usuario: str = "anonimo",
) -> str:
    """Grava a interação na tabela audit_log e retorna o id gerado."""
    auditoria_id = str(uuid.uuid4())

    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO audit_log (id, pergunta, sql_gerado, resultado_resumo, usuario, status, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (auditoria_id, pergunta, sql_gerado, resultado_resumo, usuario, status, datetime.utcnow()),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()

    return auditoria_id
