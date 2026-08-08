#!/usr/bin/env bash
# Cria os recursos AWS (API Gateway, Lambda, SQS, SNS) no LocalStack.
# Requer: AWS CLI v2 real (nao awslocal — o wrapper apresentou segfault em
# alguns setups Windows/Git Bash) e LocalStack rodando (docker compose up -d).
#
# Exporte antes de rodar:
#   export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1

set -euo pipefail

ENDPOINT="http://localhost:4566"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LAMBDA_DIR="$ROOT_DIR/lambda"

awslc() { aws --endpoint-url="$ENDPOINT" --region "$REGION" "$@"; }

echo "==> Empacotando código Lambda (zipfile do Python, sem depender do binario 'zip')..."
cd "$LAMBDA_DIR"
rm -rf package function.zip
pip install -r requirements.txt -t ./package --quiet
cp *.py ./package/
python -c "
import zipfile, os
with zipfile.ZipFile('function.zip', 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, _, files in os.walk('package'):
        for f in files:
            path = os.path.join(root, f)
            zf.write(path, os.path.relpath(path, 'package'))
"
rm -rf package

DB_PASS=$(grep DB_PASSWORD "$ROOT_DIR/.env" | cut -d= -f2)
NV_KEY=$(grep NVIDIA_API_KEY "$ROOT_DIR/.env" | cut -d= -f2)
LLM_MODEL=$(grep LLM_MODEL "$ROOT_DIR/.env" | cut -d= -f2)

echo "==> Criando fila SQS..."
QUEUE_URL=$(awslc sqs create-queue --queue-name relatorios-financeiros --query 'QueueUrl' --output text)

echo "==> Criando tópico SNS..."
TOPIC_ARN=$(awslc sns create-topic --name notificacoes-relatorios --query 'TopicArn' --output text)

echo "==> Criando função Lambda (handler principal)..."
awslc lambda create-function \
  --function-name agente-financeiro-handler \
  --runtime python3.12 --handler handler.lambda_handler \
  --zip-file fileb://function.zip \
  --role arn:aws:iam::000000000000:role/lambda-role \
  --timeout 180 --memory-size 1024 \
  --environment "Variables={SQS_QUEUE_URL=$QUEUE_URL,SNS_TOPIC_ARN=$TOPIC_ARN,AWS_ENDPOINT_URL=http://host.docker.internal:4566,AWS_REGION=$REGION,DB_HOST=host.docker.internal,DB_PORT=3306,DB_NAME=financeiro,DB_USER=app_user,DB_PASSWORD=$DB_PASS,NVIDIA_API_KEY=$NV_KEY,LLM_MODEL=$LLM_MODEL}" \
  --query 'FunctionName' --output text

echo "==> Criando função Lambda (worker SQS)..."
awslc lambda create-function \
  --function-name agente-financeiro-sqs-worker \
  --runtime python3.12 --handler sqs_worker.lambda_handler \
  --zip-file fileb://function.zip \
  --role arn:aws:iam::000000000000:role/lambda-role \
  --timeout 180 --memory-size 1024 \
  --environment "Variables={SNS_TOPIC_ARN=$TOPIC_ARN,AWS_ENDPOINT_URL=http://host.docker.internal:4566,AWS_REGION=$REGION,DB_HOST=host.docker.internal,DB_PORT=3306,DB_NAME=financeiro,DB_USER=app_user,DB_PASSWORD=$DB_PASS,NVIDIA_API_KEY=$NV_KEY,LLM_MODEL=$LLM_MODEL}" \
  --query 'FunctionName' --output text

echo "==> Criando API Gateway REST API..."
API_ID=$(awslc apigateway create-rest-api --name agente-financeiro-api --query 'id' --output text)
ROOT_ID=$(awslc apigateway get-resources --rest-api-id "$API_ID" --query 'items[0].id' --output text)
RESOURCE_ID=$(awslc apigateway create-resource --rest-api-id "$API_ID" --parent-id "$ROOT_ID" --path-part query --query 'id' --output text)

awslc apigateway put-method --rest-api-id "$API_ID" --resource-id "$RESOURCE_ID" \
  --http-method POST --authorization-type NONE > /dev/null

awslc apigateway put-integration --rest-api-id "$API_ID" --resource-id "$RESOURCE_ID" \
  --http-method POST --type AWS_PROXY --integration-http-method POST \
  --uri "arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$REGION:000000000000:function:agente-financeiro-handler/invocations" > /dev/null

awslc apigateway create-deployment --rest-api-id "$API_ID" --stage-name local > /dev/null

echo ""
echo "Recursos criados."
echo "SQS_QUEUE_URL=$QUEUE_URL"
echo "SNS_TOPIC_ARN=$TOPIC_ARN"
echo "Endpoint: $ENDPOINT/restapis/$API_ID/local/_user_request_/query"
echo ""
echo "NOTA: em alguns setups Windows/Docker Desktop o executor Docker-in-Docker da"
echo "Lambda falha com 'exec format error' (ver README > Solução de problemas"
echo "conhecidos). Nesse caso, valide invocando handler.lambda_handler() direto"
echo "em um processo Python local, apontando DB_HOST=localhost."
