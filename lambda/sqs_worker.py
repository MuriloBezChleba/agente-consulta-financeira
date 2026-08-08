"""Handler Lambda acionado pela fila SQS — processa relatórios pesados de forma assíncrona."""

import json
import os

import boto3
from dotenv import load_dotenv

from agent import responder_pergunta
from db import registrar_auditoria

load_dotenv()


def _sns_client():
    return boto3.client(
        "sns",
        endpoint_url=os.environ.get("AWS_ENDPOINT_URL"),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


def lambda_handler(event, context):
    """event segue o formato padrão de trigger SQS -> Lambda (Records[].body)."""
    sns = _sns_client()

    for registro in event.get("Records", []):
        corpo = json.loads(registro["body"])
        pergunta = corpo["pergunta"]

        resultado = responder_pergunta(pergunta)

        auditoria_id = registrar_auditoria(
            pergunta=pergunta,
            sql_gerado=resultado.get("sql_gerado"),
            resultado_resumo=resultado.get("resposta") or resultado.get("erro"),
            status=resultado["status"],
            ferramenta=resultado.get("ferramenta", "sql"),
        )

        sns.publish(
            TopicArn=os.environ["SNS_TOPIC_ARN"],
            Message=json.dumps({
                "pergunta": pergunta,
                "status": resultado["status"],
                "resposta": resultado.get("resposta"),
                "auditoria_id": auditoria_id,
            }, ensure_ascii=False),
            Subject="Relatório financeiro concluído",
        )

    return {"statusCode": 200}
