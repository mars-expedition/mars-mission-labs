# %% [markdown]
# # Demo RAG con Azure AI Search y Microsoft Agent Framework
# 
# Este notebook implementa una demo **RAG clásica y explicable**:
# 
# 1. Descarga un subconjunto libre de documentos de **misiones a Marte de la NASA**.
# 2. Extrae texto de los PDF y lo divide en fragmentos.
# 3. Genera embeddings con un modelo desplegado en Azure OpenAI / Microsoft Foundry.
# 4. Crea y llena un índice vectorial en Azure AI Search.
# 5. Expone la búsqueda híbrida como una herramienta de Microsoft Agent Framework.
# 6. Ejecuta preguntas con respuestas fundamentadas y referencias a las fuentes.
# 
# ## Arquitectura
# 
# ```text
# Usuario
#   │
#   ▼
# Microsoft Agent Framework
#   │ decide llamar a la herramienta
#   ▼
# buscar_en_base_documental()
#   │
#   ├── embedding de la consulta
#   ▼
# Azure AI Search
#   │ búsqueda híbrida: texto + vector
#   ▼
# fragmentos relevantes
#   │
#   ▼
# Modelo de chat en Azure OpenAI / Microsoft Foundry
#   │
#   ▼
# Respuesta con fuentes
# ```
# 
# > La ingestión se hace por código (“push ingestion”), por lo que esta demo no requiere Blob Storage, indexadores ni Azure Document Intelligence.
# 

# %% [markdown]
# ## 0. Preparación en Azure
# 
# ### Recursos mínimos
# 
# 1. **Grupo de recursos**.
# 2. **Azure OpenAI in Microsoft Foundry Models** o un **proyecto de Microsoft Foundry** con endpoint compatible con Azure OpenAI.
# 3. Dos deployments:
#    - Chat: `gpt-4.1-mini`, `gpt-4o-mini` u otro modelo compatible con Responses API.
#    - Embeddings: `text-embedding-3-small`.
# 4. **Azure AI Search**:
#    - `Free` sirve para una demo pequeña con carga directa.
#    - `Basic` es más conveniente para una presentación estable y para escenarios con identidad administrada/indexadores.
# 
# ### Roles RBAC para tu usuario
# 
# En el recurso de modelos/OpenAI:
# 
# - `Cognitive Services OpenAI User`
# 
# En Azure AI Search:
# 
# - `Search Service Contributor`
# - `Search Index Data Contributor`
# - `Search Index Data Reader`
# 
# Después, autentícate localmente:
# 
# ```bash
# az login
# az account set --subscription "<SUBSCRIPTION_ID_O_NOMBRE>"
# ```
# 
# ### Variables de entorno
# 
# Crea un archivo `.env` junto al notebook:
# 
# ```dotenv
# AZURE_OPENAI_ENDPOINT=https://<recurso>.openai.azure.com
# AZURE_OPENAI_API_VERSION=2025-04-01-preview
# AZURE_OPENAI_CHAT_MODEL=<nombre-del-deployment-chat>
# AZURE_OPENAI_EMBEDDING_MODEL=<nombre-del-deployment-embedding>
# 
# AZURE_SEARCH_ENDPOINT=https://<servicio>.search.windows.net
# AZURE_SEARCH_INDEX=rag-nasa-agent-demo
# 
# EMBEDDING_DIMENSIONS=1536
# MAX_PDFS=10
# ```
# 
# Los valores de `*_MODEL` son **nombres de deployments**, no necesariamente el nombre base del modelo.
# 

# %% [markdown]
# ## 1. Instalar dependencias
# 
# Se fija Microsoft Agent Framework a una versión conocida para que la demo sea reproducible.
# Después de instalar, reinicia el kernel si Jupyter lo solicita.
# 

# %%
%pip uninstall -y agent-framework agent-framework-azure-ai-search

%pip install --upgrade pip

%pip install \
  "agent-framework-core==1.8.1" \
  "agent-framework-openai==1.8.1" \
  "azure-search-documents==12.0.0" \
  "azure-identity>=1.17,<2" \
  "python-dotenv>=1.0,<2" \
  "pypdf>=5,<7" \
  "httpx>=0.27,<1" \
  "tiktoken>=0.8,<1" \
  "tenacity>=9,<10" \
  "pydantic>=2.9,<3"

# %% [markdown]
# ## 2. Cargar configuración y autenticar

# %%
import os
from pathlib import Path

from dotenv import load_dotenv
from azure.identity import AzureCliCredential

load_dotenv()

required = [
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_CHAT_MODEL",
    "AZURE_OPENAI_EMBEDDING_MODEL",
    "AZURE_SEARCH_ENDPOINT",
]

missing = [name for name in required if not os.getenv(name)]
if missing:
    raise RuntimeError(
        "Faltan variables de entorno: "
        + ", ".join(missing)
        + ". Crea el archivo .env antes de continuar."
    )

AZURE_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
AZURE_OPENAI_API_VERSION = os.getenv(
    "AZURE_OPENAI_API_VERSION", "2025-04-01-preview"
)
CHAT_MODEL = os.environ["AZURE_OPENAI_CHAT_MODEL"]
EMBEDDING_MODEL = os.environ["AZURE_OPENAI_EMBEDDING_MODEL"]

AZURE_SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"].rstrip("/")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX", "rag-nasa-agent-demo")

EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
MAX_PDFS = int(os.getenv("MAX_PDFS", "10"))

DATA_DIR = Path("data/nasa-earth-at-night")
DATA_DIR.mkdir(parents=True, exist_ok=True)

credential = AzureCliCredential()

print("Configuración cargada")
print(f"  Chat deployment:       {CHAT_MODEL}")
print(f"  Embedding deployment:  {EMBEDDING_MODEL}")
print(f"  Search index:          {AZURE_SEARCH_INDEX}")
print(f"  PDFs a descargar:      {MAX_PDFS}")


# %% [markdown]
# ## 3. Descargar el dataset
# 
# Para este caso de uso enfocado en misiones a Marte, hemos definido una lista específica de documentos oficiales de la NASA (como los Press Kits de Perseverance, Curiosity, InSight, entre otros).
# 
# El notebook descarga estos PDFs directamente desde los repositorios públicos de la NASA (JPL y NTRS) y los almacena en la carpeta local `data/mars-rag`. Además, conserva la URL pública de origen de cada documento para poder inyectarla posteriormente en las referencias (citas) de las respuestas del agente.
# 

# %%
from pathlib import Path
import re

import httpx

DATA_DIR = Path("data/mars-rag")
DATA_DIR.mkdir(parents=True, exist_ok=True)

MARS_DOCUMENTS = [
    {
        "title": "Mars 2020 Perseverance Launch Press Kit",
        "filename": "mars-2020-launch-press-kit.pdf",
        "url": (
            "https://www.jpl.nasa.gov/news/press_kits/"
            "mars_2020/download/mars_2020_launch_press_kit.pdf"
        ),
        "category": "robotic-mission",
        "mission": "Perseverance",
    },
    {
        "title": "Mars 2020 Perseverance Landing Press Kit",
        "filename": "mars-2020-landing-press-kit.pdf",
        "url": (
            "https://www.jpl.nasa.gov/news/press_kits/"
            "mars_2020/download/mars_2020_landing_press_kit.pdf"
        ),
        "category": "robotic-mission",
        "mission": "Perseverance",
    },
    {
        "title": "Mars Science Laboratory Curiosity Landing Press Kit",
        "filename": "curiosity-landing-press-kit.pdf",
        "url": (
            "https://www.jpl.nasa.gov/news/press_kits/"
            "MSLLanding.pdf"
        ),
        "category": "robotic-mission",
        "mission": "Curiosity",
    },
    {
        "title": "Mars Reconnaissance Orbiter Launch Press Kit",
        "filename": "mro-launch-press-kit.pdf",
        "url": (
            "https://www.jpl.nasa.gov/news/press_kits/"
            "mro-launch.pdf"
        ),
        "category": "robotic-mission",
        "mission": "Mars Reconnaissance Orbiter",
    },
    {
        "title": "MAVEN Press Kit",
        "filename": "maven-press-kit.pdf",
        "url": (
            "https://www.nasa.gov/wp-content/uploads/"
            "2015/03/maven_presskit_final2.pdf"
        ),
        "category": "robotic-mission",
        "mission": "MAVEN",
    },
    {
        "title": "Mars InSight Landing Press Kit",
        "filename": "insight-landing-press-kit.pdf",
        "url": (
            "https://www.jpl.nasa.gov/news/press_kits/"
            "insight/landing/download/"
            "mars_insight_landing_presskit.pdf"
        ),
        "category": "robotic-mission",
        "mission": "InSight",
    },
    {
        "title": "Phoenix Mars Lander Launch Press Kit",
        "filename": "phoenix-launch-press-kit.pdf",
        "url": (
            "https://www.jpl.nasa.gov/news/press_kits/"
            "phoenix-launch-presskit.pdf"
        ),
        "category": "robotic-mission",
        "mission": "Phoenix",
    },
    {
        "title": "Human Exploration of Mars Design Reference Architecture 5.0",
        "filename": "human-mars-dra-5.pdf",
        "url": (
            "https://ntrs.nasa.gov/api/citations/"
            "20090040343/downloads/20090040343.pdf"
        ),
        "category": "human-exploration",
        "mission": "Human Mars Architecture",
    },
    {
        "title": "NASA Human Missions to Mars",
        "filename": "nasa-human-missions-to-mars.pdf",
        "url": (
            "https://ntrs.nasa.gov/api/citations/"
            "20160013646/downloads/20160013646.pdf"
        ),
        "category": "human-exploration",
        "mission": "Human Mars Architecture",
    },
    {
        "title": "Human Exploration of Mars Preliminary Crew Tasks",
        "filename": "human-mars-crew-tasks.pdf",
        "url": (
            "https://ntrs.nasa.gov/api/citations/"
            "20190001401/downloads/20190001401.pdf"
        ),
        "category": "human-exploration",
        "mission": "Human Mars Operations",
    },
]

MAX_PDFS = min(MAX_PDFS, len(MARS_DOCUMENTS))

headers = {
    "User-Agent": "azure-rag-agent-framework-demo",
}

downloaded_files = []

with httpx.Client(
    follow_redirects=True,
    timeout=180.0,
    headers=headers,
) as client:
    for document in MARS_DOCUMENTS[:MAX_PDFS]:
        local_path = DATA_DIR / document["filename"]

        if not local_path.exists():
            print("Descargando:", document["title"])

            response = client.get(document["url"])
            response.raise_for_status()

            content_type = response.headers.get(
                "content-type",
                "",
            ).lower()

            if (
                not response.content.startswith(b"%PDF")
                and "application/pdf" not in content_type
            ):
                raise RuntimeError(
                    f'La descarga de "{document["title"]}" '
                    "no parece ser un PDF."
                )

            local_path.write_bytes(response.content)

        downloaded_files.append(
            {
                "path": local_path,
                "source_url": document["url"],
                "name": document["filename"],
                "title": document["title"],
                "category": document["category"],
                "mission": document["mission"],
                "source_page": None,
            }
        )

print(f"\nPDFs disponibles: {len(downloaded_files)}")

for document in downloaded_files:
    size_mb = document["path"].stat().st_size / 1024 / 1024

    print(
        f'- {document["title"]} '
        f'[{document["category"]}] '
        f'({size_mb:.1f} MB)'
    )

# %% [markdown]
# ## 4. Extraer texto y crear chunks
# 
# Para una demo, un chunk de aproximadamente 700 tokens con 100 tokens de solapamiento suele ofrecer un equilibrio razonable entre contexto y precisión. En producción, este valor debe evaluarse con preguntas reales.
# 

# %%
import hashlib
import re
from typing import Iterable

import tiktoken
from pypdf import PdfReader

encoding = tiktoken.get_encoding("cl100k_base")
CHUNK_TOKENS = 700
CHUNK_OVERLAP = 100


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_tokens(text: str, chunk_size: int, overlap: int) -> Iterable[str]:
    token_ids = encoding.encode(text)
    if not token_ids:
        return

    step = chunk_size - overlap
    for start in range(0, len(token_ids), step):
        chunk_ids = token_ids[start : start + chunk_size]
        if not chunk_ids:
            break
        yield encoding.decode(chunk_ids)
        if start + chunk_size >= len(token_ids):
            break


chunks = []

for document in downloaded_files:
    reader = PdfReader(str(document["path"]))

    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):
        page_text = clean_text(
            page.extract_text() or ""
        )

        if len(page_text) < 80:
            continue

        for chunk_number, chunk_text in enumerate(
            split_tokens(
                page_text,
                CHUNK_TOKENS,
                CHUNK_OVERLAP,
            ),
            start=1,
        ):
            stable_key = (
                f'{document["name"]}|'
                f'{page_number}|'
                f'{chunk_number}|'
                f'{chunk_text[:80]}'
            )

            chunk_id = hashlib.sha1(
                stable_key.encode("utf-8")
            ).hexdigest()

            chunks.append(
                {
                    "id": chunk_id,
                    "title": document["title"],
                    "content": clean_text(chunk_text),
                    "source_url": document["source_url"],
                    "page_number": page_number,
                    "category": document["category"],
                    "mission": document["mission"],
                }
            )

print("Chunks creados:", len(chunks))


# %% [markdown]
# ## 5. Generar embeddings con Microsoft Agent Framework

# %%
from agent_framework.openai import OpenAIEmbeddingClient
from tenacity import retry, stop_after_attempt, wait_exponential

embedding_client = OpenAIEmbeddingClient(
    model=EMBEDDING_MODEL,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=AZURE_OPENAI_API_VERSION,
    credential=credential,
)


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=20),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def embed_texts(texts: list[str]) -> list[list[float]]:
    generated = await embedding_client.get_embeddings(texts)
    return [list(item.vector) for item in generated]


BATCH_SIZE = 16

for start in range(0, len(chunks), BATCH_SIZE):
    batch = chunks[start : start + BATCH_SIZE]
    vectors = await embed_texts([item["content"] for item in batch])

    for item, vector in zip(batch, vectors, strict=True):
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"El embedding tiene {len(vector)} dimensiones, "
                f"pero el índice está configurado para {EMBEDDING_DIMENSIONS}."
            )
        item["content_vector"] = vector

    print(
        f"Embeddings: {min(start + BATCH_SIZE, len(chunks))}/{len(chunks)}",
        end="\r",
    )

print(f"\nEmbeddings generados: {len(chunks)}")


# %% [markdown]
# ## 6. Crear el índice vectorial en Azure AI Search

# %%
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchableField,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
    SemanticSearch,
)

index_client = SearchIndexClient(
    endpoint=AZURE_SEARCH_ENDPOINT,
    credential=credential,
)

fields = [
    SimpleField(
        name="id",
        type=SearchFieldDataType.String,
        key=True,
        filterable=True,
    ),
    SearchableField(
        name="title",
        type=SearchFieldDataType.String,
        searchable=True,
        filterable=True,
    ),
    SearchableField(
        name="content",
        type=SearchFieldDataType.String,
        searchable=True,
    ),
    SimpleField(
        name="source_url",
        type=SearchFieldDataType.String,
        filterable=True,
    ),
    SimpleField(
        name="page_number",
        type=SearchFieldDataType.Int32,
        filterable=True,
        sortable=True,
    ),
    SearchField(
        name="content_vector",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        searchable=True,
        vector_search_dimensions=EMBEDDING_DIMENSIONS,
        vector_search_profile_name="rag-vector-profile",
    ),
    SearchableField(
        name="category",
        type=SearchFieldDataType.String,
        searchable=True,
        filterable=True,
        facetable=True,
    ),
    SearchableField(
        name="mission",
        type=SearchFieldDataType.String,
        searchable=True,
        filterable=True,
        facetable=True,
    ),
]

vector_search = VectorSearch(
    algorithms=[
        HnswAlgorithmConfiguration(name="rag-hnsw"),
    ],
    profiles=[
        VectorSearchProfile(
            name="rag-vector-profile",
            algorithm_configuration_name="rag-hnsw",
        ),
    ],
)

try:
    index_client.delete_index(AZURE_SEARCH_INDEX)
    print("Índice anterior eliminado.")
except Exception:
    print("El índice no existía o no pudo eliminarse.")

semantic_config = SemanticConfiguration(
    name="rag-semantic-config",
    prioritized_fields=SemanticPrioritizedFields(
        title_field=SemanticField(field_name="title"),
        content_fields=[SemanticField(field_name="content")],
    )
)

semantic_search = SemanticSearch(configurations=[semantic_config])

index = SearchIndex(
    name=AZURE_SEARCH_INDEX,
    fields=fields,
    vector_search=vector_search,
    semantic_search=semantic_search,
)

created_index = index_client.create_or_update_index(index)
print("Índice preparado:", created_index.name)


# %% [markdown]
# ## 7. Cargar los chunks al índice

# %%
from azure.search.documents import SearchClient

search_client = SearchClient(
    endpoint=AZURE_SEARCH_ENDPOINT,
    index_name=AZURE_SEARCH_INDEX,
    credential=credential,
)

UPLOAD_BATCH_SIZE = 100
failed = []

for start in range(0, len(chunks), UPLOAD_BATCH_SIZE):
    batch = chunks[start : start + UPLOAD_BATCH_SIZE]
    results = search_client.upload_documents(documents=batch)

    failed.extend(
        [
            {
                "key": result.key,
                "error": result.error_message,
            }
            for result in results
            if not result.succeeded
        ]
    )

if failed:
    raise RuntimeError(f"Fallaron {len(failed)} documentos: {failed[:3]}")

print(f"Documentos vectoriales cargados: {len(chunks)}")


# %% [markdown]
# ## 8. Probar recuperación híbrida con Rerank (Semantic Ranker)
# 
# La consulta híbrida envía simultáneamente:
# 
# - `search_text`: coincidencia léxica BM25.
# - `vector_queries`: similitud semántica.
# Azure AI Search combina ambos rankings y aplica un paso de **Rerank (Semantic Ranker)** para reordenar los resultados utilizando modelos de lenguaje avanzados, priorizando la relevancia semántica.
# 

# %%
from azure.search.documents.models import VectorizedQuery


async def retrieve(query: str, top_k: int = 5, use_rerank: bool = True) -> list[dict]:
    query_vector = (await embed_texts([query]))[0]

    vector_query = VectorizedQuery(
        vector=query_vector,
        k_nearest_neighbors=top_k,
        fields="content_vector",
        kind="vector",
    )

    if use_rerank:
        try:
            # Intentamos usar búsqueda semántica (Rerank L2)
            results = search_client.search(
                search_text=query,
                vector_queries=[vector_query],
                select=["id", "title", "content", "source_url", "page_number"],
                top=top_k,
                query_type="semantic",
                semantic_configuration_name="rag-semantic-config",
            )
        except Exception as e:
            print(f"Advertencia: No se pudo realizar la búsqueda semántica (Rerank). Fallando al modo híbrido estándar: {e}")
            results = search_client.search(
                search_text=query,
                vector_queries=[vector_query],
                select=["id", "title", "content", "source_url", "page_number"],
                top=top_k,
            )
    else:
        results = search_client.search(
            search_text=query,
            vector_queries=[vector_query],
            select=["id", "title", "content", "source_url", "page_number"],
            top=top_k,
        )

    return [
        {
            "id": result["id"],
            "title": result["title"],
            "content": result["content"],
            "source_url": result["source_url"],
            "page_number": result["page_number"],
            "score": result.get("@search.score"),
        }
        for result in results
    ]


sample_query = "What is the Curiosity's mission?"
print("--- Recuperando con Rerank ---")
retrieved_con = await retrieve(sample_query, top_k=4, use_rerank=True)
for rank, item in enumerate(retrieved_con, start=1):
    print(f'[{rank}] {item["title"]}, página {item["page_number"]}, score={item["score"]}')
    print(item["content"][:200], "\n")

print("\n--- Recuperando sin Rerank ---")
retrieved_sin = await retrieve(sample_query, top_k=4, use_rerank=False)
for rank, item in enumerate(retrieved_sin, start=1):
    print(f'[{rank}] {item["title"]}, página {item["page_number"]}, score={item["score"]}')
    print(item["content"][:200], "\n")


# %% [markdown]
# ## 9. Convertir Azure AI Search en una herramienta del agente
# 
# La función devuelve únicamente los fragmentos recuperados. El modelo recibe instrucciones estrictas para:
# 
# - usar la herramienta antes de responder;
# - no inventar información;
# - citar título, página y URL;
# - reconocer cuando la base documental no contiene la respuesta.
# 

# %%
from typing import Annotated
from agent_framework import tool
from pydantic import Field


@tool(approval_mode="never_require")
async def buscar_en_base_documental_con_rerank(
    pregunta: Annotated[
        str,
        Field(description="Pregunta o consulta de búsqueda sobre las misiones a Marte.")
    ],
    top_k: Annotated[
        int,
        Field(description="Número de fragmentos a recuperar.", ge=1, le=8)
    ] = 5,
) -> str:
    """Busca evidencia relevante en el índice de Azure AI Search usando Rerank (Búsqueda Semántica L2)."""
    results = await retrieve(pregunta, top_k=top_k, use_rerank=True)
    if not results:
        return "NO_SE_ENCONTRO_EVIDENCIA"

    passages = []
    for i, item in enumerate(results, start=1):
        passages.append(
            f"FRAGMENTO {i}\n"
            f"Título: {item['title']}\n"
            f"Página: {item['page_number']}\n"
            f"Fuente: {item['source_url']}\n"
            f"Contenido: {item['content']}"
        )
    return "\n\n---\n\n".join(passages)


@tool(approval_mode="never_require")
async def buscar_en_base_documental_sin_rerank(
    pregunta: Annotated[
        str,
        Field(description="Pregunta o consulta de búsqueda sobre las misiones a Marte.")
    ],
    top_k: Annotated[
        int,
        Field(description="Número de fragmentos a recuperar.", ge=1, le=8)
    ] = 5,
) -> str:
    """Busca evidencia relevante en el índice usando búsqueda híbrida estándar (sin Rerank)."""
    results = await retrieve(pregunta, top_k=top_k, use_rerank=False)
    if not results:
        return "NO_SE_ENCONTRO_EVIDENCIA"

    passages = []
    for i, item in enumerate(results, start=1):
        passages.append(
            f"FRAGMENTO {i}\n"
            f"Título: {item['title']}\n"
            f"Página: {item['page_number']}\n"
            f"Fuente: {item['source_url']}\n"
            f"Contenido: {item['content']}"
        )
    return "\n\n---\n\n".join(passages)


# %% [markdown]
# ## 10. Crear y ejecutar el agente RAG

# %%
from agent_framework.openai import OpenAIChatClient

chat_client = OpenAIChatClient(
    model=CHAT_MODEL,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=None,
    credential=credential,
)

instructions = """
Eres un asistente RAG especializado en los documentos sobre misiones a Marte.

Reglas obligatorias:
1. Para cualquier pregunta factual sobre el corpus, llama primero a la herramienta de búsqueda disponible.
2. Responde solamente con información respaldada por los fragmentos recuperados.
3. Si la evidencia no es suficiente, indica claramente:
   "No encuentro evidencia suficiente en la base documental."
4. Incluye una sección final "Fuentes" con título, página y URL.
5. No inventes páginas, URLs, datos ni conclusiones.
6. Responde en el idioma de la pregunta.
7. Mantén la respuesta clara y apropiada para una demostración técnica.
"""

agent_con_rerank = chat_client.as_agent(
    name="MarsMissionsRAG_Rerank",
    instructions=instructions,
    tools=[buscar_en_base_documental_con_rerank],
)

agent_sin_rerank = chat_client.as_agent(
    name="MarsMissionsRAG_NoRerank",
    instructions=instructions,
    tools=[buscar_en_base_documental_sin_rerank],
)

question = "What is the Curiosity's mission?"

print("=== RESPUESTA CON RERANK (SEMANTIC RANKER) ===")
response_con = await agent_con_rerank.run(question)
print(response_con.text)

print("\n" + "=" * 60 + "\n")

print("=== RESPUESTA SIN RERANK (HÍBRIDO ESTÁNDAR) ===")
response_sin = await agent_sin_rerank.run(question)
print(response_sin.text)


# %% [markdown]
# ## 11. Pruebas recomendadas para la presentación
# 
# Ejecuta una pregunta de cada tipo:
# 
# 1. **Recuperable y semántica**  
#    `¿Cuál fue el objetivo principal de la misión Curiosity en Marte?`
# 
# 2. **Pregunta de síntesis**  
#    `Resume los descubrimientos clave sobre la posible presencia de agua en Marte.`
# 
# 3. **Sin palabras exactas del documento**  
#    `¿Qué indicios hay de que el planeta rojo pudo haber sido habitable en el pasado?`
# 
# 4. **Fuera del corpus / prueba de grounding**  
#    `¿Cuál es el precio actual de Bitcoin?`  
#    El agente debe reconocer que no existe evidencia suficiente.
# 
# 5. **Transparencia del RAG**  
#    Primero muestra los chunks recuperados con `retrieve()`, y después la respuesta final del agente.
# 

# %%
demo_questions = [
    "¿Cuál fue el objetivo principal de la misión Curiosity en Marte?",
    "Resume los descubrimientos clave sobre la posible presencia de agua en Marte.",
    "¿Qué indicios hay de que el planeta rojo pudo haber sido habitable en el pasado?",
    "¿Cuál es el precio actual de Bitcoin?",
]

#Descomenta para ejecutar la batería completa.
for q in demo_questions:
    print("\n" + "=" * 100)
    print("PREGUNTA:", q)
    
    print("\n--- Con Rerank (Semantic Ranker) ---")
    answer_con = await agent_con_rerank.run(q)
    print(answer_con.text)
    
    print("\n--- Sin Rerank (Híbrido Estándar) ---")
    answer_sin = await agent_sin_rerank.run(q)
    print(answer_sin.text)


# %% [markdown]
# ## 12. Qué explicar durante la demo
# 
# ### Flujo de ingestión
# 
# `PDF → texto → chunks → embeddings → documentos del índice`
# 
# ### Flujo de consulta
# 
# `pregunta → embedding → búsqueda híbrida → Rerank (Semantic Ranker) → top-k chunks → herramienta → agente → respuesta citada`
# 
# ### Diferencia entre RAG y entrenamiento
# 
# Los documentos no reentrenan el modelo. Se recuperan en tiempo de consulta y se incluyen como contexto.
# 
# ### Por qué usar un agente
# 
# Un pipeline RAG tradicional llama siempre al buscador. En esta demo, Agent Framework registra la recuperación como una herramienta y administra el ciclo de tool calling. Esto permite agregar más herramientas posteriormente, por ejemplo SQL, APIs empresariales o acciones.
# 
# ### Limitaciones que conviene mencionar
# 
# - La calidad depende del parsing, chunking, embeddings y ranking.
# - Los PDFs escaneados requerirían OCR o Azure Document Intelligence.
# - Para producción se necesitan evaluación, observabilidad, seguridad, filtros por permisos y controles contra prompt injection.
# - `Default/AzureCliCredential` es conveniente para desarrollo; en producción se recomienda una identidad administrada específica.
# 

# %% [markdown]
# ## 13. Limpieza opcional
# 
# La siguiente celda elimina el índice para evitar dejar recursos de datos. Los recursos de Azure deben eliminarse desde el grupo de recursos cuando termine la demo.
# 

# %%
# PELIGRO: descomenta únicamente cuando quieras borrar el índice.
# index_client.delete_index(AZURE_SEARCH_INDEX)
# print("Índice eliminado:", AZURE_SEARCH_INDEX)


# %% [markdown]
# ## Referencias técnicas
# 
# - Microsoft Agent Framework: https://learn.microsoft.com/agent-framework/
# - Provider Azure OpenAI / OpenAI para Agent Framework: https://learn.microsoft.com/agent-framework/agents/providers/openai
# - Azure AI Search vector quickstart: https://learn.microsoft.com/azure/search/search-get-started-vector
# - Azure AI Search sample data: https://github.com/Azure-Samples/azure-search-sample-data
# - Tutorial RAG con NASA Earth e-book: https://learn.microsoft.com/azure/search/tutorial-rag-build-solution
# 


