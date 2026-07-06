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

# 1. Clientes Base
chat_client = OpenAIChatClient(model=CHAT_MODEL, azure_endpoint=AZURE_OPENAI_ENDPOINT, api_version=CHAT_API_VERSION, credential=credential)
embedding_client = OpenAIEmbeddingClient(model=EMBEDDING_MODEL, azure_endpoint=AZURE_OPENAI_ENDPOINT, api_version=EMBEDDING_API_VERSION, credential=credential)
search_client = SearchClient(endpoint=AZURE_SEARCH_ENDPOINT, index_name=AZURE_SEARCH_INDEX, credential=credential)

# 2. Creamos la función que buscará la información en Azure Search (Rerank Habilitado)
async def recuperar_conocimiento(query: str, top_k: int = 5) -> str:
    """Traduce la pregunta a vector, busca en el índice y aplica Rerank semántico."""
    # Convertimos la pregunta de texto a Vector (Embedding)
    emb_resp = await embedding_client.get_embeddings(values=[query])
    vector = emb_resp[0].vector
    vector_query = VectorizedQuery(vector=vector, k_nearest_neighbors=10, fields="content_vector")
    
    # Realizamos búsqueda híbrida (Texto + Vector) y pasamos el resultado por el Semantic Ranker
    results = await search_client.search(
        search_text=query,
        vector_queries=[vector_query],
        select=["title", "content", "source_url", "page_number"],
        query_type="semantic",
        semantic_configuration_name="rag-semantic-config",
        top=top_k,
    )
    
    passages = []
    # Iteramos la respuesta asíncrona (AsyncItemPaged)
    async for item in results:
        passages.append(
            f"Título: {item['title']} (Pág. {item['page_number']})\n"
            f"Fuente: {item['source_url']}\n"
            f"Contenido: {item['content']}"
        )
        
    if not passages:
        return "NO_SE_ENCONTRO_EVIDENCIA"
        
    return "\n\n---\n\n".join(passages)


# 3. Empaquetamos la función como una 'Tool' (Herramienta) para el Agente
@tool(approval_mode="never_require")
async def buscar_en_base_documental(
    pregunta: Annotated[str, Field(description="Pregunta sobre misiones a Marte para buscar en la base documental.")]
) -> str:
    """Busca evidencia relevante en la base de datos de misiones a Marte."""
    print(f"\n[TOOL] El agente está buscando: '{pregunta}'...")
    return await recuperar_conocimiento(pregunta)


# 4. Construimos nuestro Agente
# Le damos una personalidad y reglas estrictas para evitar alucinaciones.
instrucciones_agente = """
Eres un asistente RAG especializado en documentos de misiones a Marte de la NASA.
Reglas:
1. Siempre llama a la herramienta de búsqueda antes de responder.
2. Responde SOLO con la información recuperada de los fragmentos.
3. Si no encuentras la respuesta, di "No encuentro evidencia suficiente".
4. Al final de tu respuesta, lista tus "Fuentes" citando el Título y la Página.
"""

agente_rag = chat_client.as_agent(
    name="MarsRAG_Agent",
    instructions=instrucciones_agente,
    tools=[buscar_en_base_documental],
)

# --- Ejecución ---
async def main():
    print("=== PROBANDO EL AGENTE RAG ===")
    pregunta = "¿Qué instrumento del rover Curiosity utiliza un láser para vaporizar rocas?"
    
    print(f"\nPregunta del Usuario: {pregunta}")
    print("Esperando que el Agente analice la pregunta, use la herramienta y formule una respuesta...\n")
    
    respuesta = await agente_rag.run(pregunta)
    
    print("\n=== RESPUESTA FINAL DEL AGENTE ===")
    print(respuesta.text)
    
    # IMPORTANTE: Cerramos la sesión del cliente de búsqueda al terminar
    await search_client.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
