"""Proveedor de contexto RAG para Microsoft Agent Framework."""

from __future__ import annotations

import logging
from typing import Any

from agent_framework import AgentSession, ContextProvider, SessionContext
from agent_framework.openai import OpenAIEmbeddingClient
from azure.search.documents.aio import SearchClient as AsyncSearchClient
from azure.search.documents.models import QueryType, VectorizedQuery

try:
    from .models import ChunkMetadata, ContextChunk
    from .search_service import normalize_page_value
except ImportError:
    from models import ChunkMetadata, ContextChunk
    from search_service import normalize_page_value

logger = logging.getLogger("rag_demo_backend.context_provider")


class AzureSearchRAGContextProvider(ContextProvider):
    """Context Provider que inyecta evidencia recuperada de Azure AI Search en el agente antes de cada turno.

    Implementa el hook oficial before_run de Microsoft Agent Framework.
    """

    def __init__(
        self,
        search_client: AsyncSearchClient,
        embedding_client: OpenAIEmbeddingClient,
        top_k: int = 3,
        use_rerank: bool = False,
    ) -> None:
        super().__init__("azure-search-rag-provider")
        self.search_client = search_client
        self.embedding_client = embedding_client
        self.top_k = max(1, min(top_k or 3, 8))
        self.use_rerank = use_rerank
        self.retrieved_chunks: list[ContextChunk] = []

    async def before_run(
        self,
        *,
        agent: Any,
        session: AgentSession,
        context: SessionContext,
        state: dict[str, Any],
    ) -> None:
        """Hook invocado antes de que el modelo procese el turno del usuario."""
        user_query = ""
        if context.input_messages:
            last_msg = context.input_messages[-1]
            user_query = getattr(last_msg, "text", "") or str(last_msg)

        if not user_query:
            return

        # 1. Crear embeddings de la consulta con el cliente del framework
        emb_resp = await self.embedding_client.get_embeddings(values=[user_query])
        vector = emb_resp[0].vector
        vector_query = VectorizedQuery(
            vector=vector, k_nearest_neighbors=self.top_k, fields="content_vector"
        )

        # 2. Búsqueda Vectorial o Híbrida Semántica en Azure Search
        search_kwargs: dict[str, Any] = {
            "search_text": user_query,
            "vector_queries": [vector_query],
            "select": ["title", "content", "source_url", "page_number"],
            "top": self.top_k,
        }
        if self.use_rerank:
            search_kwargs["query_type"] = QueryType.SEMANTIC
            search_kwargs["semantic_configuration_name"] = "rag-semantic-config"

        results_async = await self.search_client.search(**search_kwargs)

        context_docs: list[ContextChunk] = []
        passages: list[str] = []

        async for item in results_async:
            score = item.get("@search.reranker_score") or item.get("@search.score")
            score_type = "reranker_score" if item.get("@search.reranker_score") is not None else "search_score"
            chunk = ContextChunk(
                score=float(score) if score is not None else None,
                score_type=score_type,
                content=(item.get("content") or "")[:300] + "...",
                metadata=ChunkMetadata(
                    title=item.get("title"),
                    source=item.get("source_url"),
                    page=normalize_page_value(item.get("page_number")),
                ),
            )
            context_docs.append(chunk)
            passages.append(f"Documento: {item.get('title')}\nContenido: {item.get('content')}")

        self.retrieved_chunks = context_docs
        state["retrieved_chunks"] = context_docs

        context_str = "\n---\n".join(passages) if passages else "NO_SE_ENCONTRO_EVIDENCIA"

        # 3. Inyectar el contexto documental recuperado en las instrucciones del agente
        context.extend_instructions(
            self.source_id,
            "Contexto documental recuperado:\n\n"
            + context_str
            + "\n\nInstrucción: Responde de forma clara y precisa usando únicamente el contexto provisto. "
            "Si el contexto no contiene evidencia explícita suficiente, indícalo y no uses conocimiento externo.",
        )
