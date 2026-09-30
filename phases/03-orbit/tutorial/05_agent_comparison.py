import os
from pathlib import Path
from typing import Annotated
from dotenv import load_dotenv
from pydantic import Field
from azure.identity import DefaultAzureCredential
from azure.search.documents.models import VectorizedQuery
from agent_framework import tool
from agent_framework.openai import OpenAIChatClient, OpenAIEmbeddingClient
from azure.search.documents.aio import SearchClient

SCRIPT_DIR = Path(__file__).resolve().parent
PHASE_DIR = SCRIPT_DIR.parent
load_dotenv(PHASE_DIR / ".env")

AZURE_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
CHAT_MODEL = os.environ["AZURE_OPENAI_CHAT_MODEL"]
EMBEDDING_MODEL = os.environ["AZURE_OPENAI_EMBEDDING_MODEL"]
CHAT_API_VERSION = os.getenv("AZURE_OPENAI_RESPONSES_API_VERSION") or None
EMBEDDING_API_VERSION = os.getenv(
    "AZURE_OPENAI_EMBEDDING_API_VERSION",
    os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview"),
)
AZURE_SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"].rstrip("/")
AZURE_SEARCH_INDEX = os.environ["AZURE_SEARCH_INDEX"]

credential = DefaultAzureCredential()
chat_client = OpenAIChatClient(model=CHAT_MODEL, azure_endpoint=AZURE_OPENAI_ENDPOINT, api_version=CHAT_API_VERSION, credential=credential)
embedding_client = OpenAIEmbeddingClient(model=EMBEDDING_MODEL, azure_endpoint=AZURE_OPENAI_ENDPOINT, api_version=EMBEDDING_API_VERSION, credential=credential)
search_client = SearchClient(endpoint=AZURE_SEARCH_ENDPOINT, index_name=AZURE_SEARCH_INDEX, credential=credential)

GROUNDING_INSTRUCTIONS = (
    "Eres un experto RAG en misiones a Marte. Usa tu herramienta de búsqueda. "
    "Responde ÚNICAMENTE con la evidencia recuperada. "
    "Si la evidencia no menciona explícitamente la respuesta, dilo y no uses conocimiento externo."
)

async def recuperar_conocimiento(query: str, use_rerank: bool, top_k: int = 3) -> str:
    emb_resp = await embedding_client.get_embeddings(values=[query])
    vector = emb_resp[0].vector
    vector_query = VectorizedQuery(vector=vector, k_nearest_neighbors=3, fields="content_vector")
    
    if use_rerank:
        results = await search_client.search(
            search_text=query,
            vector_queries=[vector_query],
            select=["title", "content", "source_url", "page_number"],
            query_type="semantic",
            semantic_configuration_name="rag-semantic-config",
            top=top_k,
        )
    else:
        results = await search_client.search(
            search_text=query,
            vector_queries=[vector_query],
            select=["title", "content", "source_url", "page_number"],
            top=top_k,
        )
        
    passages = [f"Fuente: {item['title']} - {item['content']}" async for item in results]
    return "\n---\n".join(passages) if passages else "NO_SE_ENCONTRO_EVIDENCIA"

@tool(approval_mode="never_require")
async def buscar_sin_rerank(pregunta: Annotated[str, Field(description="Busca en la base documental sin rerank")]) -> str:
    return await recuperar_conocimiento(pregunta, use_rerank=False)

@tool(approval_mode="never_require")
async def buscar_con_rerank(pregunta: Annotated[str, Field(description="Busca en la base documental con rerank semántico")]) -> str:
    return await recuperar_conocimiento(pregunta, use_rerank=True)

# --- 1. AGENTE SIN RERANK (Búsqueda Híbrida Estándar) ---
agente_sin_rerank = chat_client.as_agent(
    name="Agent_No_Rerank",
    instructions=GROUNDING_INSTRUCTIONS,
    tools=[buscar_sin_rerank]
)

# --- 2. AGENTE CON RERANK (Semantic Ranker) ---
agente_con_rerank = chat_client.as_agent(
    name="Agent_Rerank",
    instructions=GROUNDING_INSTRUCTIONS,
    tools=[buscar_con_rerank]
)

async def main():
    pregunta = "¿Qué misión busca señales de vida antigua en el cráter Jezero?"
    
    print("\n" + "="*80)
    print(" PREGUNTA: ", pregunta)
    print("="*80)
    
    # PRUEBA 1: SIN RERANK
    print("\n--- 1. RESPUESTA SIN RERANK (Híbrido Estándar) ---")
    resp_sin_rerank = await agente_sin_rerank.run(pregunta)
    print(resp_sin_rerank.text)
    
    print("\n" + "-"*80)
    
    # PRUEBA 2: CON RERANK
    print("\n--- 2. RESPUESTA CON RERANK (Semantic Ranker L2) ---")
    resp_con_rerank = await agente_con_rerank.run(pregunta)
    print(resp_con_rerank.text)
    
    await search_client.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
