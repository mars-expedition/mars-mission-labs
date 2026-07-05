import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
        page = metadata.get("page") or metadata.get("page_number") or raw.get("page") or raw.get("page_number")
        content = raw.get("content") or raw.get("page_content") or raw.get("text") or raw.get("snippet") or ""

        chunks.append({
            "score": raw.get("score"),
            "content": content,
            "metadata": {
                "title": title,
                "source": source,
                "page": page,
            },
        })

    return chunks

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
                    "page": r.get("page_number")
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
                    "page": item.get("page_number")
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
                    "Responde de forma clara y precisa en base al siguiente contexto provisto:\n\n"
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
            payload = _extract_json_object(raw_text)
            if payload:
                answer = payload.get("answer") or raw_text
                context_docs = _normalize_agent_chunks(payload.get("chunks") or payload.get("context"))
                return {
                    "answer": answer,
                    "context": context_docs,
                    "agent": FOUNDRY_AGENT_NAME,
                    "context_source": "foundry_agent_json",
                }

            return {
                "answer": raw_text,
                "context": [],
                "agent": FOUNDRY_AGENT_NAME,
                "context_source": "foundry_agent_text"
            }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
