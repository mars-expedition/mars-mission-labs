import json
import os
from pathlib import Path

from azure.core.exceptions import HttpResponseError, ResourceExistsError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
from dotenv import load_dotenv


SCRIPT_DIR = Path(__file__).resolve().parent
PHASE_DIR = SCRIPT_DIR.parent
load_dotenv(PHASE_DIR / ".env")

DATA_DIR = PHASE_DIR / "data"
METADATA_FILE = DATA_DIR / "metadata.json"
OUTPUT_FILE = DATA_DIR / "blob_manifest.json"

def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Falta {name}. Crea o actualiza {PHASE_DIR / '.env'} con los datos "
            "de tu Storage Account antes de ejecutar este paso."
        )
    return value


AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
AZURE_STORAGE_ACCOUNT_URL = os.getenv("AZURE_STORAGE_ACCOUNT_URL")
AZURE_STORAGE_RESOURCE_ID = os.getenv("AZURE_STORAGE_RESOURCE_ID")
AZURE_STORAGE_CONTAINER = require_env("AZURE_STORAGE_CONTAINER")
AZURE_STORAGE_BLOB_PREFIX = os.getenv("AZURE_STORAGE_BLOB_PREFIX", "mars-rag").strip("/")


def is_configured(value: str | None) -> bool:
    return bool(value and "<" not in value and "..." not in value)


def create_blob_service() -> BlobServiceClient:
    if is_configured(AZURE_STORAGE_CONNECTION_STRING):
        print("Autenticando Storage con connection string.")
        return BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

    account_url = AZURE_STORAGE_ACCOUNT_URL
    if not is_configured(account_url) and is_configured(AZURE_STORAGE_ACCOUNT_NAME):
        account_url = f"https://{AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net"

    if is_configured(account_url):
        print("Autenticando Storage con Azure AD.")
        return BlobServiceClient(
            account_url=account_url,
            credential=DefaultAzureCredential(),
        )

    raise RuntimeError(
        "Falta configurar Storage. Define AZURE_STORAGE_CONNECTION_STRING o "
        "AZURE_STORAGE_ACCOUNT_NAME en el .env."
    )


def print_storage_permission_help(error: HttpResponseError) -> None:
    error_code = getattr(error, "error_code", None) or "AuthorizationPermissionMismatch"
    print("\nNo se pudo escribir el blob en Azure Storage.")
    print(f"Codigo de Azure Storage: {error_code}")
    print()
    print("Si estas usando Azure AD, tu usuario necesita el rol:")
    print("- Storage Blob Data Contributor")
    print()
    print("Scope recomendado:")
    if is_configured(AZURE_STORAGE_RESOURCE_ID):
        print(AZURE_STORAGE_RESOURCE_ID)
    elif is_configured(AZURE_STORAGE_ACCOUNT_NAME):
        print(f"Storage Account: {AZURE_STORAGE_ACCOUNT_NAME}")
    else:
        print("Storage Account configurado en el .env")
    print()
    print("Despues de asignar el rol, espera 2-5 minutos y vuelve a ejecutar este script.")


def blob_name_for(filename: str) -> str:
    if not AZURE_STORAGE_BLOB_PREFIX:
        return filename
    return f"{AZURE_STORAGE_BLOB_PREFIX}/{filename}"


def metadata_for(document: dict) -> dict:
    return {
        "title": document["title"],
        "source_url": document["url"],
        "category": document["category"],
        "mission": document["mission"],
    }


def main():
    print("--- Preparando PDFs para Azure AI Search ---")

    if not METADATA_FILE.exists():
        print("No se encontro metadata.json. Ejecuta primero 01_download_data.py")
        return

    with METADATA_FILE.open("r", encoding="utf-8") as f:
        downloaded_files = json.load(f)

    blob_service = create_blob_service()
    container_client = blob_service.get_container_client(AZURE_STORAGE_CONTAINER)

    try:
        container_client.create_container()
        print(f"Contenedor creado: {AZURE_STORAGE_CONTAINER}")
    except ResourceExistsError:
        print(f"Usando contenedor existente: {AZURE_STORAGE_CONTAINER}")

    manifest = []

    for document in downloaded_files:
        filepath = DATA_DIR / document["filename"]
        if not filepath.exists():
            print(f"Saltando archivo no encontrado: {filepath}")
            continue

        blob_name = blob_name_for(document["filename"])
        blob_client = container_client.get_blob_client(blob_name)

        print(f"Subiendo: {document['title']} -> {blob_name}")
        try:
            with filepath.open("rb") as pdf_file:
                blob_client.upload_blob(
                    pdf_file,
                    overwrite=True,
                    metadata=metadata_for(document),
                    content_settings=ContentSettings(content_type="application/pdf"),
                )
        except HttpResponseError as error:
            if getattr(error, "error_code", None) == "AuthorizationPermissionMismatch":
                print_storage_permission_help(error)
            raise

        manifest.append(
            {
                "title": document["title"],
                "filename": document["filename"],
                "blob_name": blob_name,
                "source_url": document["url"],
                "category": document["category"],
                "mission": document["mission"],
            }
        )

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\nPDFs publicados en Blob Storage: {len(manifest)}")
    print(f"Manifest guardado en: {OUTPUT_FILE}")
    print("El chunking y los embeddings se generaran en Azure AI Search con Text Split Skill.")
    print("Siguiente paso -> Ejecuta '03_setup_search_index.py'")


if __name__ == "__main__":
    main()
