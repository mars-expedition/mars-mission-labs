"""API Backend para la plataforma de demostración RAG - Misión Marte (Fase 03 - Orbit).

Expone endpoints para:
- Explorar chunks almacenados en Azure AI Search.
- Consultar un agente local con Microsoft Agent Framework y ContextProvider.
- Consultar y transmitir respuestas de un agente nativo en Azure AI Foundry.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# Microsoft Agent Framework
from agent_framework import Agent
from agent_framework.openai import OpenAIChatCompletionClient, OpenAIEmbeddingClient
from azure.search.documents.aio import SearchClient as AsyncSearchClient

# Asegurar resolución de módulos tanto al ejecutar como paquete como en modo script
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from .config import Settings, get_azure_credential, get_settings
    from .context_provider import AzureSearchRAGContextProvider
    from .foundry_service import query_foundry_agent, stream_foundry_agent
    from .models import AskResponse, DocumentsResponse, QueryRequest
    from .search_service import list_search_documents
except ImportError:
    from config import Settings, get_azure_credential, get_settings
    from context_provider import AzureSearchRAGContextProvider
    from foundry_service import query_foundry_agent, stream_foundry_agent
    from models import AskResponse, DocumentsResponse, QueryRequest
    from search_service import list_search_documents

# ---------------------------------------------------------------------------
# Logging y Aplicación FastAPI
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag_demo_backend")

settings = get_settings()

app = FastAPI(
    title="Mars Mission Labs - RAG Demo API",
    description="API para demostración de RAG con Azure AI Search y Microsoft Agent Framework",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints de la API
# ---------------------------------------------------------------------------
@app.get(
    "/api/documents",
    response_model=DocumentsResponse,
    summary="Listar fragmentos indexados en Azure AI Search",
)
def get_documents(
    current_settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentsResponse:
    """Retorna los documentos/chunks almacenados en el índice de Azure AI Search."""
    credential = get_azure_credential()
    try:
        docs = list_search_documents(current_settings, credential)
        return DocumentsResponse(documents=docs)
    except ValueError as exc:
        logger.warning("Configuración incompleta de Azure AI Search: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error al listar documentos de Azure AI Search: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post(
    "/api/ask/local",
    response_model=AskResponse,
    summary="Consultar agente local con ContextProvider",
)
async def ask_local_agent(
    req: QueryRequest,
    current_settings: Annotated[Settings, Depends(get_settings)],
) -> AskResponse:
    """Responde utilizando un agente local de Microsoft Agent Framework con ContextProvider."""
    if (
        not current_settings.azure_openai_endpoint
        or not current_settings.azure_openai_chat_model
    ):
        raise HTTPException(
            status_code=500, detail="Faltan las variables de entorno de Azure OpenAI"
        )

    credential = get_azure_credential()
    chat_client = OpenAIChatCompletionClient(
        model=current_settings.azure_openai_chat_model,
        azure_endpoint=current_settings.azure_openai_endpoint,
        api_version=current_settings.azure_openai_chat_api_version,
        credential=credential,
    )
    embedding_client = OpenAIEmbeddingClient(
        model=current_settings.azure_openai_embedding_model,
        azure_endpoint=current_settings.azure_openai_endpoint,
        api_version=current_settings.azure_openai_embedding_api_version,
        credential=credential,
    )
    search_client = AsyncSearchClient(
        endpoint=current_settings.azure_search_endpoint,
        index_name=current_settings.azure_search_index,
        credential=credential,
    )

    rag_provider = AzureSearchRAGContextProvider(
        search_client=search_client,
        embedding_client=embedding_client,
        top_k=req.top_k,
        use_rerank=req.use_rerank,
    )

    agent = Agent(
        client=chat_client,
        name="MarsLocalRAGAgent",
        instructions="Eres un asistente RAG experto en misiones a Marte de la NASA.",
        context_providers=[rag_provider],
    )

    try:
        response = await agent.run(req.query)
        answer = response.text or ""
    except Exception as exc:
        logger.exception("Error durante la ejecución del agente local: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await search_client.close()

    return AskResponse(
        answer=answer,
        context=rag_provider.retrieved_chunks,
        use_rerank=req.use_rerank,
    )


@app.post(
    "/api/ask/foundry",
    response_model=AskResponse,
    summary="Consultar agente nativo de Azure AI Foundry",
)
def ask_foundry_agent(
    req: QueryRequest,
    current_settings: Annotated[Settings, Depends(get_settings)],
) -> AskResponse:
    """Responde utilizando el Agente Nativo desplegado en Azure AI Foundry."""
    credential = get_azure_credential()
    try:
        return query_foundry_agent(req, current_settings, credential)
    except ValueError as exc:
        logger.warning("Configuración incompleta de Azure AI Foundry: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error al invocar el agente Foundry: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post(
    "/api/ask/foundry/stream",
    summary="Transmitir respuesta del agente Foundry como Server-Sent Events (SSE)",
)
def ask_foundry_agent_stream(
    req: QueryRequest,
    current_settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    """Transmite la respuesta del agente Foundry como Server-Sent Events (SSE)."""
    credential = get_azure_credential()
    return StreamingResponse(
        stream_foundry_agent(req, current_settings, credential),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
