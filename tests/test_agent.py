import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda"))

import pytest

from db import validar_query_somente_leitura, QueryNotAllowedError


def test_select_simples_e_permitido():
    validar_query_somente_leitura("SELECT * FROM clientes")


def test_select_case_insensitive_e_permitido():
    validar_query_somente_leitura("select nome from clientes where id = 1")


@pytest.mark.parametrize("sql_malicioso", [
    "DELETE FROM clientes",
    "UPDATE ativos SET valor = 0",
    "DROP TABLE audit_log",
    "INSERT INTO clientes (nome) VALUES ('x')",
    "SELECT * FROM clientes; DROP TABLE clientes;",
])
def test_operacoes_de_escrita_sao_bloqueadas(sql_malicioso):
    with pytest.raises(QueryNotAllowedError):
        validar_query_somente_leitura(sql_malicioso)


def test_query_sem_select_no_inicio_e_bloqueada():
    with pytest.raises(QueryNotAllowedError):
        validar_query_somente_leitura("WITH x AS (DELETE FROM clientes) SELECT * FROM x")
