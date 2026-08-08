"""Handler Lambda acionado pelo API Gateway (POST /query)."""

import json
import os

import boto3
from dotenv import load_dotenv

from agent import responder_pergunta
from db import registrar_auditoria

load_dotenv()


def _sqs_client():
    return boto3.client(
        "sqs",
        endpoint_url=os.environ.get("AWS_ENDPOINT_URL"),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


def _resposta_http(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def lambda_handler(event, context):
    try:
        payload = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _resposta_http(400, {"erro": "JSON inválido no corpo da requisição."})

    pergunta = payload.get("pergunta")
    modo = payload.get("modo", "sincrono")

    if not pergunta:
        return _resposta_http(400, {"erro": "Campo 'pergunta' é obrigatório."})

    if modo == "assincrono":
        sqs = _sqs_client()
        envio = sqs.send_message(
            QueueUrl=os.environ["SQS_QUEUE_URL"],
            MessageBody=json.dumps({"pergunta": pergunta}, ensure_ascii=False),
        )
        return _resposta_http(202, {"status": "processando", "job_id": envio["MessageId"]})

    resultado = responder_pergunta(pergunta)

    auditoria_id = registrar_auditoria(
        pergunta=pergunta,
        sql_gerado=resultado.get("sql_gerado"),
        resultado_resumo=resultado.get("resposta") or resultado.get("erro"),
        status=resultado["status"],
    )

    if resultado["status"] == "bloqueado":
        return _resposta_http(400, {"erro": resultado["erro"], "auditoria_id": auditoria_id})

    return _resposta_http(200, {
        "resposta": resultado["resposta"],
        "sql_gerado": resultado["sql_gerado"],
        "auditoria_id": auditoria_id,
    })
