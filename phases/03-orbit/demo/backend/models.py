"""Modelos de datos (Pydantic DTOs) para la API del backend."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    """Solicitud de consulta RAG enviada por el frontend."""

    model_config = ConfigDict(extra="ignore")

    query: str = Field(..., min_length=1, description="Pregunta del usuario")
    top_k: int = Field(default=3, ge=1, le=10, description="Número de fragmentos a recuperar")
    use_rerank: bool = Field(default=False, description="Habilitar Semantic Reranker de Azure")


class ChunkMetadata(BaseModel):
    """Metadatos asociados a un fragmento documental."""

    model_config = ConfigDict(extra="ignore")

    title: Optional[str] = Field(default=None, description="Título del documento")
    source: Optional[str] = Field(default=None, description="URL o fuente del documento")
    page: Optional[str] = Field(default=None, description="Número de página normalizado")
    line: Optional[str] = Field(default=None, description="Línea o referencia interna")


class ContextChunk(BaseModel):
    """Fragmento de contexto documental recuperado con score opcional."""

    model_config = ConfigDict(extra="ignore")

    score: Optional[float] = Field(default=None, description="Puntaje de relevancia del fragmento")
    score_type: Optional[str] = Field(default=None, description="Tipo de score: reranker_score o search_score")
    rank: Optional[int] = Field(default=None, description="Posición en el ranking de recuperación")
    content: str = Field(default="", description="Contenido textual del fragmento")
    metadata: ChunkMetadata = Field(default_factory=ChunkMetadata, description="Metadatos del fragmento")


class DocumentItem(BaseModel):
    """Documento o fragmento indexado en Azure AI Search."""

    model_config = ConfigDict(extra="ignore")

    id: Optional[str] = Field(default=None, description="Identificador único en Azure Search")
    content: str = Field(default="", description="Snippet del contenido del documento")
    metadata: ChunkMetadata = Field(default_factory=ChunkMetadata, description="Metadatos del documento")


class DocumentsResponse(BaseModel):
    """Respuesta con la lista de fragmentos almacenados en el índice."""

    documents: list[DocumentItem] = Field(default_factory=list, description="Lista de fragmentos")


class AskResponse(BaseModel):
    """Respuesta a una consulta enviada a un agente RAG."""

    model_config = ConfigDict(extra="ignore")

    answer: str = Field(..., description="Respuesta textual generada por el agente")
    context: list[ContextChunk] = Field(default_factory=list, description="Fragmentos de evidencia utilizados")
    use_rerank: Optional[bool] = Field(default=None, description="Indica si se utilizó reranking semántico")
    agent: Optional[str] = Field(default=None, description="Identificador del agente evaluado")
    context_source: Optional[str] = Field(default=None, description="Estrategia u origen del contexto recuperado")
