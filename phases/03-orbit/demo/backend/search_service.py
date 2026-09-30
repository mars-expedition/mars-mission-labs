"""Servicio de interacción con Azure AI Search y normalización de chunks."""

from __future__ import annotations

import logging
from typing import Any, Optional

from azure.search.documents import SearchClient
from azure.search.documents.models import QueryType

try:
    from .config import Settings
    from .models import ChunkMetadata, ContextChunk, DocumentItem
except ImportError:
    from config import Settings
    from models import ChunkMetadata, ContextChunk, DocumentItem

logger = logging.getLogger("rag_demo_backend.search_service")


def first_present(*values: Any) -> Any:
    """Retorna el primer valor no nulo de la secuencia."""
    for value in values:
        if value is not None:
            return value
    return None


def coerce_float(value: Any) -> Optional[float]:
    """Convierte un valor a float o retorna None si no es numérico."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_page_value(value: Any) -> Optional[str]:
    """Normaliza un valor de página a cadena limpia o None si es inválido."""
    if value is None:
        return None
    if isinstance(value, list):
        return None
    if isinstance(value, (int, float)):
        return str(int(value))

    text = str(value).strip()
    if not text or "," in text:
        return None
    return text


def normalize_agent_chunks(raw_chunks: Any) -> list[ContextChunk]:
    """Convierte una lista heterogénea de fragmentos devueltos por un agente en objetos ContextChunk."""
    if not isinstance(raw_chunks, list):
        return []

    chunks: list[ContextChunk] = []
    for raw in raw_chunks:
        if isinstance(raw, ContextChunk):
            chunks.append(raw)
            continue
        if not isinstance(raw, dict):
            continue

        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        source = (
            metadata.get("source")
            or metadata.get("source_url")
            or raw.get("source")
            or raw.get("source_url")
        )
        title = (
            metadata.get("title")
            or raw.get("title")
            or "Documento recuperado de la base de datos"
        )
        page = normalize_page_value(
            metadata.get("page")
            or metadata.get("page_number")
            or raw.get("page")
            or raw.get("page_number")
        )
        content = (
            raw.get("content")
            or raw.get("page_content")
            or raw.get("text")
            or raw.get("snippet")
            or ""
        )
        score = coerce_float(
            first_present(
                raw.get("score"),
                metadata.get("score"),
                raw.get("@search.reranker_score"),
                raw.get("@search.score"),
            )
        )
        score_type = first_present(
            raw.get("score_type"),
            metadata.get("score_type"),
            "reranker_score" if raw.get("@search.reranker_score") is not None else None,
            "search_score" if raw.get("@search.score") is not None else None,
        )

        chunk = ContextChunk(
            score=score,
            score_type=score_type,
            content=content,
            metadata=ChunkMetadata(
                title=title,
                source=source,
                page=page,
            ),
        )
        chunks.append(chunk)

    return chunks


def _chunk_match_key(chunk: ContextChunk) -> tuple[str, str, str]:
    title = str(chunk.metadata.title or "").strip().lower()
    source = str(chunk.metadata.source or "").strip().lower()
    page = str(chunk.metadata.page or "").strip().lower()
    return title, source, page


def _content_matches(left: ContextChunk, right: ContextChunk) -> bool:
    left_text = str(left.content or "").strip().lower()
    right_text = str(right.content or "").strip().lower()
    if not left_text or not right_text:
        return False
    return left_text[:160] in right_text or right_text[:160] in left_text


def merge_chunk_scores(
    agent_chunks: list[ContextChunk], scored_chunks: list[ContextChunk]
) -> list[ContextChunk]:
    """Combina los fragmentos devueltos por el agente con los scores de Azure Search."""
    if not scored_chunks:
        return agent_chunks
    if not agent_chunks:
        return scored_chunks

    scored_by_key = {
        _chunk_match_key(chunk): chunk
        for chunk in scored_chunks
        if any(_chunk_match_key(chunk))
    }
    used_ids: set[int] = set()
    merged: list[ContextChunk] = []

    for chunk in agent_chunks:
        merged_chunk = chunk.model_copy(deep=True)

        if merged_chunk.score is not None:
            merged.append(merged_chunk)
            continue

        match = scored_by_key.get(_chunk_match_key(merged_chunk))
        if match is None:
            match = next(
                (
                    candidate
                    for candidate in scored_chunks
                    if id(candidate) not in used_ids and _content_matches(merged_chunk, candidate)
                ),
                None,
            )

        if match:
            used_ids.add(id(match))
            merged_chunk.score = match.score
            merged_chunk.score_type = match.score_type
            merged_chunk.rank = match.rank
            if not merged_chunk.content:
                merged_chunk.content = match.content

            if not merged_chunk.metadata.title:
                merged_chunk.metadata.title = match.metadata.title
            if not merged_chunk.metadata.source:
                merged_chunk.metadata.source = match.metadata.source
            if not merged_chunk.metadata.page:
                merged_chunk.metadata.page = match.metadata.page

        merged.append(merged_chunk)

    return merged


def list_search_documents(settings: Settings, credential: Any) -> list[DocumentItem]:
    """Consulta y lista los documentos almacenados en el índice de Azure AI Search."""
    if not settings.azure_search_endpoint or not settings.azure_search_index:
        raise ValueError("Faltan las variables de entorno de Azure AI Search")

    search_client = SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index,
        credential=credential,
    )
    try:
        results = search_client.search(
            search_text="*",
            select=["id", "content", "title", "source_url", "page_number"],
            top=500,
        )
        return [
            DocumentItem(
                id=r.get("id"),
                content=(r.get("content") or "")[:250] + "...",
                metadata=ChunkMetadata(
                    title=r.get("title"),
                    source=r.get("source_url"),
                    page=normalize_page_value(r.get("page_number")),
                ),
            )
            for r in results
        ]
    finally:
        search_client.close()


def retrieve_scored_chunks(
    query: str, top_k: int, settings: Settings, credential: Any
) -> list[ContextChunk]:
    """Consulta Azure AI Search directamente para obtener fragmentos clasificados con sus scores."""
    if not settings.azure_search_endpoint or not settings.azure_search_index:
        return []

    top_k = max(1, min(top_k or 3, 8))
    search_client = SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index,
        credential=credential,
    )
    select_fields = ["id", "content", "title", "source_url", "page_number"]

    try:
        try:
            results = search_client.search(
                search_text=query,
                select=select_fields,
                query_type=QueryType.SEMANTIC,
                semantic_configuration_name="rag-semantic-config",
                top=top_k,
            )
        except Exception:
            results = search_client.search(
                search_text=query,
                select=select_fields,
                top=top_k,
            )

        chunks: list[ContextChunk] = []
        for rank, item in enumerate(results, start=1):
            reranker_score = item.get("@search.reranker_score")
            search_score = item.get("@search.score")
            score = coerce_float(first_present(reranker_score, search_score))
            score_type = "reranker_score" if reranker_score is not None else "search_score"

            chunks.append(
                ContextChunk(
                    rank=rank,
                    score=score,
                    score_type=score_type,
                    content=(item.get("content") or "")[:300] + "...",
                    metadata=ChunkMetadata(
                        title=item.get("title"),
                        source=item.get("source_url"),
                        page=normalize_page_value(item.get("page_number")),
                    ),
                )
            )
        return chunks
    except Exception as exc:
        logger.error("Error al consultar Azure AI Search para scored chunks: %s", exc)
        return []
    finally:
        search_client.close()
