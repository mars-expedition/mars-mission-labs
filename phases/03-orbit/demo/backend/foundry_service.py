"""Servicio de integración con agentes nativos de Azure AI Foundry y streaming SSE."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Generator, Optional

from azure.ai.projects import AIProjectClient

try:
    from .config import Settings
    from .models import AskResponse, ContextChunk, QueryRequest
    from .search_service import (
        merge_chunk_scores,
        normalize_agent_chunks,
        retrieve_scored_chunks,
    )
except ImportError:
    from config import Settings
    from models import AskResponse, ContextChunk, QueryRequest
    from search_service import (
        merge_chunk_scores,
        normalize_agent_chunks,
        retrieve_scored_chunks,
    )

logger = logging.getLogger("rag_demo_backend.foundry_service")


def format_sse(event: str, data: dict[str, Any]) -> str:
    """Formatea un mensaje como Server-Sent Event (SSE)."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def extract_json_object(text: str) -> Optional[dict[str, Any]]:
    """Extrae un objeto JSON de una respuesta textual, incluso si viene en bloques markdown."""
    if not text:
        return None

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None


class JsonAnswerDeltaExtractor:
    """Extractor progresivo del campo 'answer' desde un streaming de JSON."""

    def __init__(self) -> None:
        self.buffer = ""
        self.read_pos = 0
        self.answer_started = False
        self.answer_done = False
        self.escape = False
        self.unicode_buffer: Optional[str] = None

    def feed(self, text: str) -> str:
        """Procesa un fragmento de texto y emite los caracteres decodificados de 'answer'."""
        if self.answer_done or not text:
            return ""

        self.buffer += text
        if not self.answer_started:
            match = re.search(r'"answer"\s*:\s*"', self.buffer)
            if not match:
                return ""
            self.answer_started = True
            self.read_pos = match.end()

        emitted: list[str] = []
        while self.read_pos < len(self.buffer) and not self.answer_done:
            char = self.buffer[self.read_pos]
            self.read_pos += 1

            if self.unicode_buffer is not None:
                self.unicode_buffer += char
                if len(self.unicode_buffer) == 4:
                    try:
                        emitted.append(chr(int(self.unicode_buffer, 16)))
                    except ValueError:
                        emitted.append("\\u" + self.unicode_buffer)
                    self.unicode_buffer = None
                    self.escape = False
                continue

            if self.escape:
                if char == "u":
                    self.unicode_buffer = ""
                    continue

                emitted.append({
                    '"': '"',
                    "\\": "\\",
                    "/": "/",
                    "b": "\b",
                    "f": "\f",
                    "n": "\n",
                    "r": "\r",
                    "t": "\t",
                }.get(char, char))
                self.escape = False
                continue

            if char == "\\":
                self.escape = True
                continue

            if char == '"':
                self.answer_done = True
                break

            emitted.append(char)

        return "".join(emitted)


def _stream_event_type(event: Any) -> str:
    if isinstance(event, dict):
        return event.get("type") or event.get("event") or ""
    return getattr(event, "type", None) or getattr(event, "event", None) or ""


def _stream_event_delta(event: Any) -> str:
    event_type = _stream_event_type(event)
    if event_type and "delta" not in event_type:
        return ""

    if isinstance(event, dict):
        delta = event.get("delta") or event.get("text")
    else:
        delta = getattr(event, "delta", None) or getattr(event, "text", None)

    return delta if isinstance(delta, str) else ""


def _response_output_text(response: Any) -> str:
    if response is None:
        return ""
    if isinstance(response, dict):
        return response.get("output_text") or ""
    return getattr(response, "output_text", None) or ""


def _completed_response_from_event(event: Any) -> Any:
    if isinstance(event, dict):
        return event.get("response")
    return getattr(event, "response", None)


def query_foundry_agent(
    req: QueryRequest, settings: Settings, credential: Any
) -> AskResponse:
    """Invoca sincrónicamente el agente nativo de Azure AI Foundry y correlaciona chunks."""
    if not settings.foundry_project_endpoint:
        raise ValueError("Falta FOUNDRY_PROJECT_ENDPOINT en la configuración")

    project_client = AIProjectClient(
        endpoint=settings.foundry_project_endpoint, credential=credential
    )
    with project_client:
        openai_client = project_client.get_openai_client()
        conversation = openai_client.conversations.create()
        response = openai_client.responses.create(
            conversation=conversation.id,
            input=req.query,
            extra_body={
                "agent_reference": {
                    "name": settings.foundry_agent_name,
                    "type": "agent_reference",
                }
            },
        )

        raw_text = response.output_text or ""
        scored_chunks = retrieve_scored_chunks(
            req.query, req.top_k, settings, credential
        )
        payload = extract_json_object(raw_text)

        if payload:
            answer = payload.get("answer") or raw_text
            context_docs = normalize_agent_chunks(
                payload.get("chunks") or payload.get("context")
            )
            context_docs = merge_chunk_scores(context_docs, scored_chunks)
            return AskResponse(
                answer=answer,
                context=context_docs,
                agent=settings.foundry_agent_name,
                context_source="foundry_agent_json_with_search_scores",
            )

        return AskResponse(
            answer=raw_text,
            context=scored_chunks,
            agent=settings.foundry_agent_name,
            context_source="azure_search_score_fallback",
        )


def stream_foundry_agent(
    req: QueryRequest, settings: Settings, credential: Any
) -> Generator[str, None, None]:
    """Generador que transmite eventos SSE en tiempo real desde el agente Foundry."""
    scored_chunks: list[ContextChunk] = []
    try:
        if not settings.foundry_project_endpoint:
            yield format_sse("error", {"detail": "Falta FOUNDRY_PROJECT_ENDPOINT en la configuración"})
            return

        scored_chunks = retrieve_scored_chunks(
            req.query, req.top_k, settings, credential
        )
        if scored_chunks:
            yield format_sse("context", {
                "context": [c.model_dump() for c in scored_chunks],
                "context_source": "azure_search_score_fallback",
            })

        project_client = AIProjectClient(
            endpoint=settings.foundry_project_endpoint, credential=credential
        )
        raw_parts: list[str] = []
        pending = ""
        stream_mode: Optional[str] = None
        json_answer = JsonAnswerDeltaExtractor()
        answer_done_sent = False

        with project_client:
            openai_client = project_client.get_openai_client()
            conversation = openai_client.conversations.create()
            create_kwargs = {
                "conversation": conversation.id,
                "input": req.query,
                "extra_body": {
                    "agent_reference": {
                        "name": settings.foundry_agent_name,
                        "type": "agent_reference",
                    }
                },
            }

            try:
                stream = openai_client.responses.create(**create_kwargs, stream=True)
                for event in stream:
                    delta = _stream_event_delta(event)
                    if delta:
                        raw_parts.append(delta)
                        pending += delta

                        if stream_mode is None:
                            stripped = pending.lstrip()
                            if not stripped:
                                continue
                            if stripped.startswith("{") or stripped.startswith("```"):
                                stream_mode = "json"
                                answer_delta = json_answer.feed(pending)
                                pending = ""
                                if answer_delta:
                                    yield format_sse("delta", {"delta": answer_delta})
                                if json_answer.answer_done and not answer_done_sent:
                                    answer_done_sent = True
                                    yield format_sse("answer_done", {
                                        "context": [c.model_dump() for c in scored_chunks]
                                    })
                            else:
                                stream_mode = "plain"
                                yield format_sse("delta", {"delta": pending})
                                pending = ""
                        elif stream_mode == "json":
                            answer_delta = json_answer.feed(delta)
                            if answer_delta:
                                yield format_sse("delta", {"delta": answer_delta})
                            if json_answer.answer_done and not answer_done_sent:
                                answer_done_sent = True
                                yield format_sse("answer_done", {
                                    "context": [c.model_dump() for c in scored_chunks]
                                })
                        else:
                            yield format_sse("delta", {"delta": delta})

                    completed_text = _response_output_text(_completed_response_from_event(event))
                    if completed_text and not raw_parts:
                        raw_parts.append(completed_text)
            except Exception:
                response = openai_client.responses.create(**create_kwargs)
                raw_text = _response_output_text(response)
                raw_parts = [raw_text]

        raw_text = "".join(raw_parts)
        payload = extract_json_object(raw_text)
        if payload:
            answer = payload.get("answer") or raw_text
            context_docs = normalize_agent_chunks(payload.get("chunks") or payload.get("context"))
            context_docs = merge_chunk_scores(context_docs, scored_chunks)
            if not answer_done_sent:
                yield format_sse("answer_done", {
                    "context": [c.model_dump() for c in context_docs]
                })
            yield format_sse("final", {
                "answer": answer,
                "context": [c.model_dump() for c in context_docs],
                "agent": settings.foundry_agent_name,
                "context_source": "foundry_agent_json_with_search_scores",
            })
        else:
            if not answer_done_sent:
                yield format_sse("answer_done", {
                    "context": [c.model_dump() for c in scored_chunks]
                })
            yield format_sse("final", {
                "answer": raw_text,
                "context": [c.model_dump() for c in scored_chunks],
                "agent": settings.foundry_agent_name,
                "context_source": "azure_search_score_fallback",
            })
    except Exception as exc:
        logger.exception("Error en streaming del agente Foundry: %s", exc)
        yield format_sse("error", {"detail": str(exc)})
