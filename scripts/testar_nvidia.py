"""Script de teste manual — confirma que a chave NVIDIA_API_KEY funciona.
Nao faz parte da aplicacao (Lambda), e so pra validar localmente. Nao commitar chave nenhuma."""

import os

from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import ChatNVIDIA

load_dotenv()

client = ChatNVIDIA(
    model=os.environ.get("LLM_MODEL", "meta/llama-3.1-8b-instruct"),
    api_key=os.environ["NVIDIA_API_KEY"],
    temperature=0.2,
    top_p=0.7,
    max_tokens=256,
    timeout=120,
)

response = client.invoke([{"role": "user", "content": "Diga oi em uma frase curta."}])
print(response.content)
