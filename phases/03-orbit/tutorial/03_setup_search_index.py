import os
import time
from pathlib import Path

import httpx
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv


SCRIPT_DIR = Path(__file__).resolve().parent
PHASE_DIR = SCRIPT_DIR.parent
load_dotenv(PHASE_DIR / ".env")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Falta {name}. Crea o actualiza {PHASE_DIR / '.env'} antes de ejecutar este paso."
        )
    return value


AZURE_SEARCH_ENDPOINT = require_env("AZURE_SEARCH_ENDPOINT").rstrip("/")
AZURE_SEARCH_INDEX = require_env("AZURE_SEARCH_INDEX")
AZURE_SEARCH_API_VERSION = os.getenv("AZURE_SEARCH_API_VERSION", "2025-09-01")

AZURE_OPENAI_ENDPOINT = require_env("AZURE_OPENAI_ENDPOINT").rstrip("/")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_EMBEDDING_MODEL = require_env("AZURE_OPENAI_EMBEDDING_MODEL")
AZURE_OPENAI_EMBEDDING_MODEL_NAME = os.getenv(
    "AZURE_OPENAI_EMBEDDING_MODEL_NAME",
    AZURE_OPENAI_EMBEDDING_MODEL,
)
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))

AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID")
AZURE_RESOURCE_GROUP = os.getenv("AZURE_RESOURCE_GROUP")
AZURE_STORAGE_ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
AZURE_STORAGE_RESOURCE_ID = os.getenv("AZURE_STORAGE_RESOURCE_ID")
AZURE_STORAGE_CONTAINER = require_env("AZURE_STORAGE_CONTAINER")
AZURE_STORAGE_BLOB_PREFIX = os.getenv("AZURE_STORAGE_BLOB_PREFIX", "mars-rag").strip("/")

TEXT_SPLIT_MODE = os.getenv("AZURE_SEARCH_TEXT_SPLIT_MODE", "pages")
TEXT_SPLIT_UNIT = os.getenv("AZURE_SEARCH_TEXT_SPLIT_UNIT", "characters")
TEXT_SPLIT_MAX_LENGTH = int(os.getenv("AZURE_SEARCH_TEXT_SPLIT_MAX_LENGTH", "3500"))
TEXT_SPLIT_OVERLAP = int(os.getenv("AZURE_SEARCH_TEXT_SPLIT_OVERLAP", "500"))
TEXT_SPLIT_LANGUAGE = os.getenv("AZURE_SEARCH_TEXT_SPLIT_LANGUAGE", "en")

RESET_SEARCH_ASSETS = os.getenv("RESET_SEARCH_ASSETS", "true").lower() == "true"
WAIT_FOR_INDEXER = os.getenv("WAIT_FOR_INDEXER", "true").lower() == "true"

DATA_SOURCE_NAME = f"{AZURE_SEARCH_INDEX}-blob-datasource"
SKILLSET_NAME = f"{AZURE_SEARCH_INDEX}-textsplit-skillset"
INDEXER_NAME = f"{AZURE_SEARCH_INDEX}-blob-indexer"


def is_configured(value: str | None) -> bool:
    return bool(value and "<" not in value and "..." not in value)


def search_url(path: str) -> str:
    separator = "&" if "?" in path else "?"
    return f"{AZURE_SEARCH_ENDPOINT}{path}{separator}api-version={AZURE_SEARCH_API_VERSION}"


def resource_path(collection: str, name: str) -> str:
    return f"/{collection}('{name}')"


def create_search_client() -> httpx.Client:
    token = DefaultAzureCredential().get_token("https://search.azure.com/.default").token
    return httpx.Client(
        timeout=120.0,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )


def request_search(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    expected: tuple[int, ...] = (200, 201, 202, 204),
    ignore_404: bool = False,
) -> httpx.Response | None:
    response = client.request(method, search_url(path), json=json_body)
    if ignore_404 and response.status_code == 404:
        return None
    if response.status_code not in expected:
        raise RuntimeError(
            f"{method} {path} fallo con HTTP {response.status_code}:\n{response.text}"
        )
    return response


def index_definition() -> dict:
    return {
        "name": AZURE_SEARCH_INDEX,
        "fields": [
            {
                "name": "id",
                "type": "Edm.String",
                "key": True,
                "searchable": True,
                "filterable": True,
                "retrievable": True,
                "analyzer": "keyword",
            },
            {"name": "parent_id", "type": "Edm.String", "filterable": True},
            {
                "name": "title",
                "type": "Edm.String",
                "searchable": True,
                "filterable": True,
                "sortable": True,
                "retrievable": True,
            },
            {
                "name": "content",
                "type": "Edm.String",
                "searchable": True,
                "retrievable": True,
            },
            {
                "name": "source_url",
                "type": "Edm.String",
                "filterable": True,
                "retrievable": True,
            },
            {
                "name": "page_number",
                "type": "Edm.String",
                "filterable": True,
                "sortable": True,
                "retrievable": True,
            },
            {
                "name": "category",
                "type": "Edm.String",
                "searchable": True,
                "filterable": True,
                "facetable": True,
                "retrievable": True,
            },
            {
                "name": "mission",
                "type": "Edm.String",
                "searchable": True,
                "filterable": True,
                "facetable": True,
                "retrievable": True,
            },
            {
                "name": "content_vector",
                "type": "Collection(Edm.Single)",
                "searchable": True,
                "retrievable": False,
                "dimensions": EMBEDDING_DIMENSIONS,
                "vectorSearchProfile": "rag-vector-profile",
            },
        ],
        "vectorSearch": {
            "algorithms": [
                {
                    "name": "rag-hnsw",
                    "kind": "hnsw",
                    "hnswParameters": {"metric": "cosine"},
                }
            ],
            "profiles": [
                {
                    "name": "rag-vector-profile",
                    "algorithm": "rag-hnsw",
                }
            ],
        },
        "semantic": {
            "configurations": [
                {
                    "name": "rag-semantic-config",
                    "prioritizedFields": {
                        "titleField": {"fieldName": "title"},
                        "prioritizedContentFields": [{"fieldName": "content"}],
                    },
                }
            ]
        },
    }


def data_source_definition() -> dict:
    container = {"name": AZURE_STORAGE_CONTAINER}
    if AZURE_STORAGE_BLOB_PREFIX:
        container["query"] = AZURE_STORAGE_BLOB_PREFIX

    return {
        "name": DATA_SOURCE_NAME,
        "type": "azureblob",
        "credentials": {"connectionString": storage_data_source_connection_string()},
        "container": container,
    }


def storage_resource_id() -> str | None:
    if is_configured(AZURE_STORAGE_RESOURCE_ID):
        return AZURE_STORAGE_RESOURCE_ID

    if (
        is_configured(AZURE_SUBSCRIPTION_ID)
        and is_configured(AZURE_RESOURCE_GROUP)
        and is_configured(AZURE_STORAGE_ACCOUNT_NAME)
    ):
        return (
            f"/subscriptions/{AZURE_SUBSCRIPTION_ID}"
            f"/resourceGroups/{AZURE_RESOURCE_GROUP}"
            f"/providers/Microsoft.Storage/storageAccounts/{AZURE_STORAGE_ACCOUNT_NAME}"
        )

    return None


def storage_data_source_connection_string() -> str:
    if is_configured(AZURE_STORAGE_CONNECTION_STRING):
        return AZURE_STORAGE_CONNECTION_STRING

    resource_id = storage_resource_id()
    if resource_id:
        return f"ResourceId={resource_id};"

    raise RuntimeError(
        "Falta configurar el origen de Blob Storage para Azure AI Search. Define "
        "AZURE_STORAGE_CONNECTION_STRING o AZURE_STORAGE_RESOURCE_ID. Tambien puedes "
        "definir AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP y AZURE_STORAGE_ACCOUNT_NAME."
    )


def skillset_definition() -> dict:
    split_skill = {
        "@odata.type": "#Microsoft.Skills.Text.SplitSkill",
        "name": "split-content",
        "description": "Divide el contenido del PDF en fragmentos listos para RAG.",
        "context": "/document",
        "textSplitMode": TEXT_SPLIT_MODE,
        "maximumPageLength": TEXT_SPLIT_MAX_LENGTH,
        "pageOverlapLength": TEXT_SPLIT_OVERLAP,
        "defaultLanguageCode": TEXT_SPLIT_LANGUAGE,
        "inputs": [{"name": "text", "source": "/document/content"}],
        "outputs": [
            {"name": "textItems", "targetName": "pages"},
        ],
    }

    if TEXT_SPLIT_UNIT != "characters":
        if "preview" not in AZURE_SEARCH_API_VERSION:
            raise RuntimeError(
                "AZURE_SEARCH_TEXT_SPLIT_UNIT distinto de 'characters' requiere una "
                "API preview de Azure AI Search. Para la demo estable usa "
                "AZURE_SEARCH_TEXT_SPLIT_UNIT=characters o elimina esa variable."
            )
        split_skill["unit"] = TEXT_SPLIT_UNIT

    embedding_skill = {
        "@odata.type": "#Microsoft.Skills.Text.AzureOpenAIEmbeddingSkill",
        "name": "embed-pages",
        "description": "Genera embeddings para cada chunk creado por Text Split.",
        "context": "/document/pages/*",
        "resourceUri": AZURE_OPENAI_ENDPOINT,
        "deploymentId": AZURE_OPENAI_EMBEDDING_MODEL,
        "modelName": AZURE_OPENAI_EMBEDDING_MODEL_NAME,
        "dimensions": EMBEDDING_DIMENSIONS,
        "inputs": [{"name": "text", "source": "/document/pages/*"}],
        "outputs": [{"name": "embedding", "targetName": "content_vector"}],
    }

    if AZURE_OPENAI_API_KEY:
        embedding_skill["apiKey"] = AZURE_OPENAI_API_KEY

    return {
        "name": SKILLSET_NAME,
        "description": "Chunking nativo con Azure AI Search Text Split y embeddings en Azure OpenAI.",
        "skills": [
            split_skill,
            embedding_skill,
        ],
        "indexProjections": {
            "selectors": [
                {
                    "targetIndexName": AZURE_SEARCH_INDEX,
                    "parentKeyFieldName": "parent_id",
                    "sourceContext": "/document/pages/*",
                    "mappings": [
                        {"name": "content", "source": "/document/pages/*"},
                        {
                            "name": "content_vector",
                            "source": "/document/pages/*/content_vector",
                        },
                        {"name": "title", "source": "/document/title"},
                        {"name": "source_url", "source": "/document/source_url"},
                        {"name": "category", "source": "/document/category"},
                        {"name": "mission", "source": "/document/mission"},
                    ],
                }
            ],
            "parameters": {"projectionMode": "skipIndexingParentDocuments"},
        },
    }


def indexer_definition() -> dict:
    return {
        "name": INDEXER_NAME,
        "dataSourceName": DATA_SOURCE_NAME,
        "targetIndexName": AZURE_SEARCH_INDEX,
        "skillsetName": SKILLSET_NAME,
        "parameters": {
            "configuration": {
                "dataToExtract": "contentAndMetadata",
                "parsingMode": "default",
                "indexedFileNameExtensions": ".pdf",
            }
        },
    }


def reset_assets(client: httpx.Client) -> None:
    if not RESET_SEARCH_ASSETS:
        return

    print("Recreando recursos de Azure AI Search...")
    for path in (
        resource_path("indexers", INDEXER_NAME),
        resource_path("skillsets", SKILLSET_NAME),
        resource_path("datasources", DATA_SOURCE_NAME),
        resource_path("indexes", AZURE_SEARCH_INDEX),
    ):
        request_search(client, "DELETE", path, ignore_404=True)


def run_indexer(client: httpx.Client) -> None:
    response = client.post(search_url(f"{resource_path('indexers', INDEXER_NAME)}/search.run"))
    if response.status_code == 409:
        print("El indexer ya esta en ejecucion.")
        return
    if response.status_code not in (200, 202, 204):
        raise RuntimeError(
            f"POST {resource_path('indexers', INDEXER_NAME)}/search.run "
            f"fallo con HTTP {response.status_code}:\n"
            f"{response.text}"
        )


def wait_for_indexer(client: httpx.Client) -> None:
    if not WAIT_FOR_INDEXER:
        print("Indexer iniciado. Puedes revisar el estado en Azure Portal.")
        return

    print("Esperando a que termine el indexer...")
    for _ in range(30):
        response = request_search(
            client,
            "GET",
            f"{resource_path('indexers', INDEXER_NAME)}/search.status",
        )
        status = response.json()
        last_result = status.get("lastResult") or {}
        indexer_status = last_result.get("status") or status.get("status")

        if indexer_status:
            processed = last_result.get("itemsProcessed", 0)
            failed = last_result.get("itemsFailed", 0)
            print(f"Estado: {indexer_status} | procesados={processed} | fallidos={failed}")

        if indexer_status in {"success", "transientFailure", "persistentFailure"}:
            errors = last_result.get("errors") or []
            warnings = last_result.get("warnings") or []
            for warning in warnings[:5]:
                print(f"Advertencia: {warning.get('message', warning)}")
            for error in errors[:5]:
                print(f"Error: {error.get('message', error)}")
            if indexer_status != "success":
                raise RuntimeError("El indexer termino con errores. Revisa el detalle anterior.")
            return

        time.sleep(10)

    print("El indexer sigue en ejecucion. Revisa el progreso en Azure Portal.")


def main():
    print("--- Configurando Azure AI Search con Text Split Skill ---")
    print(f"Indice: {AZURE_SEARCH_INDEX}")
    print(f"Data source: {DATA_SOURCE_NAME}")
    print(f"Skillset: {SKILLSET_NAME}")
    print(f"Indexer: {INDEXER_NAME}")
    if not is_configured(AZURE_STORAGE_CONNECTION_STRING):
        print(
            "Storage datasource: usando ResourceId. Asegurate de que Azure AI Search "
            "tenga identidad administrada y rol Storage Blob Data Reader sobre el Storage Account."
        )

    with create_search_client() as client:
        reset_assets(client)

        print("Creando indice vectorial...")
        request_search(
            client,
            "PUT",
            resource_path("indexes", AZURE_SEARCH_INDEX),
            json_body=index_definition(),
        )

        print("Creando data source hacia Azure Blob Storage...")
        request_search(
            client,
            "PUT",
            resource_path("datasources", DATA_SOURCE_NAME),
            json_body=data_source_definition(),
        )

        print("Creando skillset con Text Split + Azure OpenAI Embeddings...")
        request_search(
            client,
            "PUT",
            resource_path("skillsets", SKILLSET_NAME),
            json_body=skillset_definition(),
        )

        print("Creando indexer...")
        request_search(
            client,
            "PUT",
            resource_path("indexers", INDEXER_NAME),
            json_body=indexer_definition(),
        )

        print("Ejecutando indexer...")
        run_indexer(client)
        wait_for_indexer(client)

    print("\nTodo el conocimiento ya esta indexado con chunking nativo de Azure AI Search.")
    print("Siguiente paso -> Ejecuta '04_agent_with_rag.py'")


if __name__ == "__main__":
    main()
