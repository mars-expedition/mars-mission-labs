import os
import json
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents import SearchClient
from azure.core.exceptions import ResourceExistsError

# Importamos las clases necesarias para definir la estructura de nuestro índice en Azure Search
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
    SemanticSearch
)

# 1. Cargamos las variables de entorno
load_dotenv()
AZURE_SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"].rstrip("/")
AZURE_SEARCH_INDEX = os.environ["AZURE_SEARCH_INDEX"]
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))

DATA_FILE = "data/chunks_embedded.json"

def main():
    print("--- Conectando a Azure AI Search ---")
    credential = DefaultAzureCredential()

    # Cliente para crear/modificar el índice
    index_client = SearchIndexClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        credential=credential
    )

    # 2. Definimos la estructura (esquema) de nuestra base de datos vectorial
    fields = [
        # El ID debe ser un String único.
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        # SearchableField significa que se puede buscar por texto normal (palabras clave) en él.
        SearchableField(name="title", type=SearchFieldDataType.String),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="source_url", type=SearchFieldDataType.String),
        SimpleField(name="page_number", type=SearchFieldDataType.String),
        # SearchField de tipo Collection(Single) es donde guardaremos nuestro vector de embeddings.
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=EMBEDDING_DIMENSIONS,
            vector_search_profile_name="my-vector-profile"
        )
    ]

    # 3. Configuramos cómo se hará la búsqueda matemática (HNSW es un algoritmo rápido de aproximación de vectores)
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="my-hnsw-config")],
        profiles=[VectorSearchProfile(name="my-vector-profile", algorithm_configuration_name="my-hnsw-config")]
    )

    # 4. Configuramos el Semantic Ranker (Rerank L2)
    # Le indicamos a Azure cuáles campos contienen el contenido y título principal para que
    # su modelo de lenguaje interno pueda recalificarlos inteligentemente.
    semantic_config = SemanticConfiguration(
        name="rag-semantic-config",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="title"),
            content_fields=[SemanticField(field_name="content")]
        )
    )
    semantic_search = SemanticSearch(configurations=[semantic_config])

    # 5. Creamos la especificación del índice
    index = SearchIndex(
        name=AZURE_SEARCH_INDEX,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search
    )

    print(f"Creando índice '{AZURE_SEARCH_INDEX}'...")
    try:
        index_client.create_index(index)
        print("Índice creado exitosamente.")
    except ResourceExistsError:
        print("El índice ya existía. Saltando creación.")

    # 6. Subir los datos al índice
    print(f"\nCargando datos desde {DATA_FILE}...")
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        documents = json.load(f)

    # Cliente para subir o buscar documentos (Data Plane)
    search_client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX,
        credential=credential
    )

    print(f"Subiendo {len(documents)} fragmentos vectorizados a Azure Search...")
    # Usamos upload_documents para enviar todo el paquete.
    result = search_client.upload_documents(documents=documents)
    print(f"¡Carga completada! {len(result)} documentos procesados.")
    
    print("\nTodo el conocimiento ya está en la nube.")
    print("Siguiente paso -> Ejecuta '04_agent_with_rag.py'")

if __name__ == "__main__":
    main()
