#!/usr/bin/env bash
# Cria os recursos AWS (API Gateway, Lambda, SQS, SNS) no LocalStack.
# Requer: awslocal (pip install awscli-local) e LocalStack rodando (docker-compose up -d localstack).

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
LAMBDA_DIR="$(dirname "$0")/../lambda"

echo "==> Empacotando código Lambda..."
cd "$LAMBDA_DIR"
pip install -r requirements.txt -t ./package --quiet
cp *.py ./package/
cd package && zip -r ../function.zip . -x "*.pyc" > /dev/null
cd ..
rm -rf package

echo "==> Criando fila SQS..."
QUEUE_URL=$(awslocal sqs create-queue --queue-name relatorios-financeiros --region "$REGION" \
  --query 'QueueUrl' --output text)
echo "SQS_QUEUE_URL=$QUEUE_URL"

echo "==> Criando tópico SNS..."
TOPIC_ARN=$(awslocal sns create-topic --name notificacoes-relatorios --region "$REGION" \
  --query 'TopicArn' --output text)
echo "SNS_TOPIC_ARN=$TOPIC_ARN"

echo "==> Criando função Lambda (handler principal)..."
awslocal lambda create-function \
  --function-name agente-financeiro-handler \
  --runtime python3.12 \
  --handler handler.lambda_handler \
  --zip-file fileb://function.zip \
  --role arn:aws:iam::000000000000:role/lambda-role \
  --region "$REGION" \
  --environment "Variables={SQS_QUEUE_URL=$QUEUE_URL,SNS_TOPIC_ARN=$TOPIC_ARN}"

echo "==> Criando função Lambda (worker SQS)..."
awslocal lambda create-function \
  --function-name agente-financeiro-sqs-worker \
  --runtime python3.12 \
  --handler sqs_worker.lambda_handler \
  --zip-file fileb://function.zip \
  --role arn:aws:iam::000000000000:role/lambda-role \
  --region "$REGION" \
  --environment "Variables={SNS_TOPIC_ARN=$TOPIC_ARN}"

echo "==> Criando API Gateway REST API..."
API_ID=$(awslocal apigateway create-rest-api --name agente-financeiro-api --region "$REGION" \
  --query 'id' --output text)
echo "API_ID=$API_ID"

echo ""
echo "Recursos criados. Atualize seu .env com os valores de SQS_QUEUE_URL e SNS_TOPIC_ARN acima."
echo "Endpoint local do LocalStack: http://localhost:4566"
