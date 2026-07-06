import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import json
import traceback

BACKEND_DIR = Path(__file__).resolve().parent
DEMO_DIR = BACKEND_DIR.parent
PHASE_DIR = DEMO_DIR.parent

sys.path.append(str(DEMO_DIR))

for env_path in (PHASE_DIR / ".env", DEMO_DIR / ".env"):
    if env_path.exists():
        load_dotenv(env_path)
        break

class QueryRequest(BaseModel):
    query: str
    top_k: int = 3
    use_rerank: bool = False

app = FastAPI(title="RAG Demo API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient

AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")
FOUNDRY_AGENT_NAME = os.getenv("FOUNDRY_AGENT_NAME", "marsrag-native-agent")


def _first_present(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _coerce_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_page_value(value):
    if value is None:
        return None

    if isinstance(value, list):
        # A projected ordinalPositions array is not a real page/chunk location.
        # Hide it instead of showing a misleading "Chunk 1" on every card.
        return None

    if isinstance(value, (int, float)):
        return str(int(value))

    text = str(value).strip()
    if not text:
        return None

    if "," in text:
        return None

    if text.isdigit():
        return text

    return text


def _extract_json_object(text: str) -> dict | None:
    """Best-effort parser for agent JSON output that may be wrapped in prose or fences."""
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


def _normalize_agent_chunks(raw_chunks) -> list[dict]:
    if not isinstance(raw_chunks, list):
        return []

    chunks = []
    for raw in raw_chunks:
        if not isinstance(raw, dict):
            continue

        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        source = metadata.get("source") or metadata.get("source_url") or raw.get("source") or raw.get("source_url")
        title = metadata.get("title") or raw.get("title") or "Documento recuperado de la base de datos"
        page = _normalize_page_value(metadata.get("page") or metadata.get("page_number") or raw.get("page") or raw.get("page_number"))
        content = raw.get("content") or raw.get("page_content") or raw.get("text") or raw.get("snippet") or ""
        score = _coerce_float(
            _first_present(
                raw.get("score"),
                metadata.get("score"),
                raw.get("@search.reranker_score"),
                raw.get("@search.score"),
            )
        )
        score_type = _first_present(
            raw.get("score_type"),
            metadata.get("score_type"),
            "reranker_score" if raw.get("@search.reranker_score") is not None else None,
            "search_score" if raw.get("@search.score") is not None else None,
        )

        chunk = {
            "score": score,
            "content": content,
            "metadata": {
                "title": title,
                "source": source,
                "page": page,
            },
        }
        if score_type:
            chunk["score_type"] = score_type
        chunks.append(chunk)

    return chunks


def _chunk_match_key(chunk: dict) -> tuple[str, str, str]:
    metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
    title = str(metadata.get("title") or chunk.get("title") or "").strip().lower()
    source = str(metadata.get("source") or metadata.get("source_url") or chunk.get("source") or chunk.get("source_url") or "").strip().lower()
    page = str(_normalize_page_value(metadata.get("page") or metadata.get("page_number") or chunk.get("page") or chunk.get("page_number")) or "").strip().lower()
    return title, source, page


def _content_matches(left: dict, right: dict) -> bool:
    left_text = str(left.get("content") or "").strip().lower()
    right_text = str(right.get("content") or "").strip().lower()
    if not left_text or not right_text:
        return False
    left_sample = left_text[:160]
    right_sample = right_text[:160]
    return left_sample in right_text or right_sample in left_text


def _merge_chunk_scores(agent_chunks: list[dict], scored_chunks: list[dict]) -> list[dict]:
    if not scored_chunks:
        return agent_chunks
    if not agent_chunks:
        return scored_chunks

    scored_by_key = {
        _chunk_match_key(chunk): chunk
        for chunk in scored_chunks
        if any(_chunk_match_key(chunk))
    }
    used_ids = set()
    merged = []

    for chunk in agent_chunks:
        merged_chunk = {
            **chunk,
            "metadata": {
                **(chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {})
            },
        }

        if _coerce_float(merged_chunk.get("score")) is not None:
            merged_chunk["score"] = _coerce_float(merged_chunk.get("score"))
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
            merged_chunk["score"] = match.get("score")
            merged_chunk["score_type"] = match.get("score_type")
            merged_chunk["rank"] = match.get("rank")
            if not merged_chunk.get("content"):
                merged_chunk["content"] = match.get("content", "")

            match_metadata = match.get("metadata") if isinstance(match.get("metadata"), dict) else {}
            for key in ("title", "source", "page"):
                if not merged_chunk["metadata"].get(key):
                    merged_chunk["metadata"][key] = match_metadata.get(key)

        merged.append(merged_chunk)

    return merged


def _retrieve_scored_chunks(query: str, top_k: int = 3) -> list[dict]:
    if not AZURE_SEARCH_ENDPOINT or not AZURE_SEARCH_INDEX:
        return []

    top_k = max(1, min(top_k or 3, 8))
    search_client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX,
        credential=DefaultAzureCredential(),
    )
    select_fields = ["id", "content", "title", "source_url", "page_number"]

    try:
        try:
            from azure.search.documents.models import QueryType

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

        chunks = []
        for rank, item in enumerate(results, start=1):
            reranker_score = item.get("@search.reranker_score")
            search_score = item.get("@search.score")
            score = _coerce_float(_first_present(reranker_score, search_score))
            score_type = "reranker_score" if reranker_score is not None else "search_score"

            chunks.append({
                "rank": rank,
                "score": score,
                "score_type": score_type,
                "content": (item.get("content") or "")[:300] + "...",
                "metadata": {
                    "title": item.get("title"),
                    "source": item.get("source_url"),
                    "page": _normalize_page_value(item.get("page_number")),
                },
            })
        return chunks
    except Exception:
        traceback.print_exc()
        return []
    finally:
        search_client.close()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class JsonAnswerDeltaExtractor:
    def __init__(self):
        self.buffer = ""
        self.read_pos = 0
        self.answer_started = False
        self.answer_done = False
        self.escape = False
        self.unicode_buffer = None

    def feed(self, text: str) -> str:
        if self.answer_done or not text:
            return ""

        self.buffer += text
        if not self.answer_started:
            import re

            match = re.search(r'"answer"\s*:\s*"', self.buffer)
            if not match:
                return ""
            self.answer_started = True
            self.read_pos = match.end()

        emitted = []
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


def _stream_event_type(event) -> str:
    if isinstance(event, dict):
        return event.get("type") or event.get("event") or ""
    return getattr(event, "type", None) or getattr(event, "event", None) or ""


def _stream_event_delta(event) -> str:
    event_type = _stream_event_type(event)
    if event_type and "delta" not in event_type:
        return ""

    if isinstance(event, dict):
        delta = event.get("delta") or event.get("text")
    else:
        delta = getattr(event, "delta", None) or getattr(event, "text", None)

    return delta if isinstance(delta, str) else ""


def _response_output_text(response) -> str:
    if response is None:
        return ""
    if isinstance(response, dict):
        return response.get("output_text") or ""
    return getattr(response, "output_text", None) or ""


def _completed_response_from_event(event):
    if isinstance(event, dict):
        return event.get("response")
    return getattr(event, "response", None)


@app.get("/api/documents")
def get_documents():
    """Returns a list of documents/chunks stored in Azure AI Search."""
    try:
        search_client = SearchClient(
            endpoint=AZURE_SEARCH_ENDPOINT,
            index_name=AZURE_SEARCH_INDEX,
            credential=DefaultAzureCredential()
        )
        # Búsqueda de todos los documentos limitando la respuesta (aumentado a 500 para la vista web)
        results = search_client.search(search_text="*", select=["id", "content", "title", "source_url", "page_number"], top=500)
        docs = []
        for r in results:
            docs.append({
                "id": r.get("id"),
                "content": r.get("content", "")[:250] + "...", 
                "metadata": {
                    "title": r.get("title"),
                    "source": r.get("source_url"),
                    "page": _normalize_page_value(r.get("page_number"))
                }
            })
        return {"documents": docs}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ask/local")
async def ask_local_agent(req: QueryRequest):
    """Answers using MAF (Microsoft Agent Framework) + Azure Search SDK (Local execution)."""
    try:
        from azure.identity import DefaultAzureCredential
        from agent_framework import Message
        from agent_framework.openai import OpenAIChatCompletionClient, OpenAIEmbeddingClient
        from azure.search.documents.aio import SearchClient
        from azure.search.documents.models import VectorizedQuery, QueryType
        
        AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT").rstrip("/")
        CHAT_MODEL = os.getenv("AZURE_OPENAI_CHAT_COMPLETION_MODEL") or os.getenv("AZURE_OPENAI_CHAT_MODEL")
        EMBEDDING_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL")
        EMBEDDING_API_VERSION = os.getenv("AZURE_OPENAI_EMBEDDING_API_VERSION") or os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
        CHAT_API_VERSION = os.getenv("AZURE_OPENAI_CHAT_COMPLETION_API_VERSION", "2024-02-15-preview")
        
        credential = DefaultAzureCredential()
        
        # Instanciar clientes MAF
        chat_client = OpenAIChatCompletionClient(model=CHAT_MODEL, azure_endpoint=AZURE_OPENAI_ENDPOINT, api_version=CHAT_API_VERSION, credential=credential)
        embedding_client = OpenAIEmbeddingClient(model=EMBEDDING_MODEL, azure_endpoint=AZURE_OPENAI_ENDPOINT, api_version=EMBEDDING_API_VERSION, credential=credential)
        
        # Instanciar cliente Azure Search asíncrono
        search_client = SearchClient(endpoint=AZURE_SEARCH_ENDPOINT, index_name=AZURE_SEARCH_INDEX, credential=credential)
        
        # 1. Crear Embeddings con MAF
        emb_resp = await embedding_client.get_embeddings(values=[req.query])
        vector = emb_resp[0].vector
        vector_query = VectorizedQuery(vector=vector, k_nearest_neighbors=3, fields="content_vector")
        
        # 2. Búsqueda Vectorial / Híbrida Semántica usando Azure Search nativo
        if req.use_rerank:
            results_async = await search_client.search(
                search_text=req.query,
                vector_queries=[vector_query],
                select=["title", "content", "source_url", "page_number"],
                query_type=QueryType.SEMANTIC,
                semantic_configuration_name="rag-semantic-config",
                top=3
            )
        else:
            results_async = await search_client.search(
                search_text=req.query,
                vector_queries=[vector_query],
                select=["title", "content", "source_url", "page_number"],
                top=3
            )
            
        context_docs = []
        passages = []
        
        async for item in results_async:
            score = item.get("@search.reranker_score") or item.get("@search.score")
            context_docs.append({
                "score": score,
                "content": item["content"][:300] + "...",
                "metadata": {
                    "title": item.get("title"),
                    "source": item.get("source_url"),
                    "page": _normalize_page_value(item.get("page_number"))
                }
            })
            passages.append(f"Documento: {item.get('title')}\nContenido: {item.get('content')}")
            
        await search_client.close()
        
        context_str = "\n---\n".join(passages) if passages else "NO_SE_ENCONTRO_EVIDENCIA"
        
        # 3. Generación de respuesta (RAG) usando MAF Chat Client
        messages = [
            Message(
                "system",
                [
                    "Eres un asistente RAG experto en misiones a Marte. "
                    "Responde de forma clara y precisa usando únicamente el contexto provisto. "
                    "Si el contexto no contiene evidencia explícita suficiente, dilo y no uses conocimiento externo:\n\n"
                    + context_str
                ],
            ),
            Message("user", [req.query]),
        ]
        
        response = await chat_client.get_response(messages=messages, options={"temperature": 0})
        answer = response.text
        
        return {
            "answer": answer,
            "context": context_docs,
            "use_rerank": req.use_rerank
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ask/foundry")
def ask_foundry_agent(req: QueryRequest):
    """Answers using Azure AI Foundry Native Agent."""
    try:
        from azure.identity import DefaultAzureCredential
        from azure.ai.projects import AIProjectClient
        
        PROJECT_ENDPOINT = os.getenv("FOUNDRY_PROJECT_ENDPOINT") or os.getenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT")
        
        credential = DefaultAzureCredential()
        project_client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential)
        
        with project_client:
            # Usar el Agente Nativo desplegado en Foundry. La version actualizada del agente
            # devuelve JSON con answer + chunks + metadata.
            openai_client = project_client.get_openai_client()
            conversation = openai_client.conversations.create()
            response = openai_client.responses.create(
                conversation=conversation.id,
                input=req.query,
                extra_body={"agent_reference": {"name": FOUNDRY_AGENT_NAME, "type": "agent_reference"}}
            )
            
            raw_text = response.output_text or ""
            scored_chunks = _retrieve_scored_chunks(req.query, req.top_k)
            payload = _extract_json_object(raw_text)
            if payload:
                answer = payload.get("answer") or raw_text
                context_docs = _normalize_agent_chunks(payload.get("chunks") or payload.get("context"))
                context_docs = _merge_chunk_scores(context_docs, scored_chunks)
                return {
                    "answer": answer,
                    "context": context_docs,
                    "agent": FOUNDRY_AGENT_NAME,
                    "context_source": "foundry_agent_json_with_search_scores",
                }

            return {
                "answer": raw_text,
                "context": scored_chunks,
                "agent": FOUNDRY_AGENT_NAME,
                "context_source": "azure_search_score_fallback"
            }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ask/foundry/stream")
def ask_foundry_agent_stream(req: QueryRequest):
    """Streams Foundry agent responses as Server-Sent Events and enriches chunks with Search scores."""

    def generate():
        scored_chunks = []
        try:
            from azure.identity import DefaultAzureCredential
            from azure.ai.projects import AIProjectClient

            PROJECT_ENDPOINT = os.getenv("FOUNDRY_PROJECT_ENDPOINT") or os.getenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT")

            scored_chunks = _retrieve_scored_chunks(req.query, req.top_k)
            if scored_chunks:
                yield _sse("context", {
                    "context": scored_chunks,
                    "context_source": "azure_search_score_fallback",
                })

            credential = DefaultAzureCredential()
            project_client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential)
            raw_parts = []
            pending = ""
            stream_mode = None
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
                            "name": FOUNDRY_AGENT_NAME,
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
                                        yield _sse("delta", {"delta": answer_delta})
                                    if json_answer.answer_done and not answer_done_sent:
                                        answer_done_sent = True
                                        yield _sse("answer_done", {"context": scored_chunks})
                                else:
                                    stream_mode = "plain"
                                    yield _sse("delta", {"delta": pending})
                                    pending = ""
                            elif stream_mode == "json":
                                answer_delta = json_answer.feed(delta)
                                if answer_delta:
                                    yield _sse("delta", {"delta": answer_delta})
                                if json_answer.answer_done and not answer_done_sent:
                                    answer_done_sent = True
                                    yield _sse("answer_done", {"context": scored_chunks})
                            else:
                                yield _sse("delta", {"delta": delta})

                        completed_text = _response_output_text(_completed_response_from_event(event))
                        if completed_text and not raw_parts:
                            raw_parts.append(completed_text)
                except Exception:
                    response = openai_client.responses.create(**create_kwargs)
                    raw_text = _response_output_text(response)
                    raw_parts = [raw_text]

            raw_text = "".join(raw_parts)
            payload = _extract_json_object(raw_text)
            if payload:
                answer = payload.get("answer") or raw_text
                context_docs = _normalize_agent_chunks(payload.get("chunks") or payload.get("context"))
                context_docs = _merge_chunk_scores(context_docs, scored_chunks)
                if not answer_done_sent:
                    answer_done_sent = True
                    yield _sse("answer_done", {"context": context_docs})
                yield _sse("final", {
                    "answer": answer,
                    "context": context_docs,
                    "agent": FOUNDRY_AGENT_NAME,
                    "context_source": "foundry_agent_json_with_search_scores",
                })
            else:
                if not answer_done_sent:
                    answer_done_sent = True
                    yield _sse("answer_done", {"context": scored_chunks})
                yield _sse("final", {
                    "answer": raw_text,
                    "context": scored_chunks,
                    "agent": FOUNDRY_AGENT_NAME,
                    "context_source": "azure_search_score_fallback",
                })
        except Exception as e:
            traceback.print_exc()
            yield _sse("error", {"detail": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
