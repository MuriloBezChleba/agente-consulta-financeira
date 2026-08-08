"""Camada de RAG (Retrieval-Augmented Generation) sobre documentos de política de
investimento. Usado quando a pergunta é conceitual/normativa (não sobre dados
transacionais especificos, que ficam a cargo de db.py + agent.gerar_sql).
"""

import os
from pathlib import Path

from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

DOCUMENTOS_DIR = Path(__file__).parent.parent / "db" / "documentos"

_vectorstore = None  # cache em memoria, construido no primeiro uso (por execution environment)


def _get_embedder() -> NVIDIAEmbeddings:
    return NVIDIAEmbeddings(
        model=os.environ.get("EMBEDDING_MODEL", "nvidia/nv-embedqa-e5-v5"),
        api_key=os.environ["NVIDIA_API_KEY"],
    )


def _carregar_documentos() -> list[str]:
    textos = []
    for arquivo in sorted(DOCUMENTOS_DIR.glob("*.md")):
        textos.append(arquivo.read_text(encoding="utf-8"))
    return textos


def _construir_indice() -> FAISS:
    documentos = _carregar_documentos()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.create_documents(documentos)
    return FAISS.from_documents(chunks, _get_embedder())


def _get_vectorstore() -> FAISS:
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = _construir_indice()
    return _vectorstore


def buscar_contexto(pergunta: str, k: int = 3) -> str:
    """Retorna os k trechos mais relevantes dos documentos de política para a pergunta."""
    vectorstore = _get_vectorstore()
    resultados = vectorstore.similarity_search(pergunta, k=k)
    if not resultados:
        return ""
    return "\n\n---\n\n".join(doc.page_content for doc in resultados)
