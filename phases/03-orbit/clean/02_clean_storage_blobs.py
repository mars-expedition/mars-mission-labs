import argparse
import os

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from _common import add_yes_arg, confirm, load_phase_env, print_header, require_env, truthy


def is_configured(value: str | None) -> bool:
    return bool(value and "<" not in value and "..." not in value)


def create_blob_service() -> BlobServiceClient:
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if is_configured(connection_string):
        return BlobServiceClient.from_connection_string(connection_string)

    account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL")
    account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
    if not is_configured(account_url) and is_configured(account_name):
        account_url = f"https://{account_name}.blob.core.windows.net"

    if is_configured(account_url):
        return BlobServiceClient(
            account_url=account_url,
            credential=DefaultAzureCredential(),
        )

    raise RuntimeError(
        "Falta configurar Storage. Define AZURE_STORAGE_CONNECTION_STRING o "
        "AZURE_STORAGE_ACCOUNT_NAME en el .env."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Elimina blobs publicados por la demo RAG en Azure Blob Storage."
    )
    add_yes_arg(parser)
    parser.add_argument(
        "--delete-container",
        action="store_true",
        help="Elimina el contenedor completo en vez de solo los blobs del prefijo.",
    )
    parser.add_argument(
        "--allow-empty-prefix",
        action="store_true",
        help="Permite borrar blobs desde la raiz del contenedor si no hay prefijo.",
    )
    args = parser.parse_args()

    load_phase_env()
    env = require_env("AZURE_STORAGE_CONTAINER")

    container_name = env["AZURE_STORAGE_CONTAINER"]
    blob_prefix = os.getenv("AZURE_STORAGE_BLOB_PREFIX", "mars-rag").strip("/")
    delete_container = args.delete_container or truthy(
        os.getenv("CLEAN_DELETE_STORAGE_CONTAINER"),
        default=False,
    )

    print_header("02 - Limpieza de Azure Blob Storage")
    print("Contenedor:", container_name)
    print("Prefijo:", blob_prefix or "(raiz del contenedor)")
    print("Eliminar contenedor completo:", delete_container)

    if not blob_prefix and not delete_container and not args.allow_empty_prefix:
        raise RuntimeError(
            "AZURE_STORAGE_BLOB_PREFIX esta vacio. Para borrar desde la raiz usa "
            "--allow-empty-prefix o --delete-container."
        )

    blob_service = create_blob_service()
    container_client = blob_service.get_container_client(container_name)

    try:
        container_client.get_container_properties()
    except ResourceNotFoundError:
        print("El contenedor no existe. Nada que limpiar.")
        return

    if delete_container:
        if not confirm("\nEsta accion eliminara el contenedor completo.", yes=args.yes):
            print("Cancelado.")
            return
        container_client.delete_container()
        print(f"Contenedor eliminado: {container_name}")
        return

    prefix_filter = f"{blob_prefix}/" if blob_prefix else None
    blobs = list(container_client.list_blobs(name_starts_with=prefix_filter))
    print(f"Blobs encontrados: {len(blobs)}")

    if not blobs:
        print("No hay blobs que eliminar.")
        return

    if not confirm("\nEsta accion eliminara los blobs listados por el prefijo.", yes=args.yes):
        print("Cancelado.")
        return

    for blob in blobs:
        container_client.delete_blob(blob.name)
        print(f"- eliminado: {blob.name}")

    print("\nBlob Storage quedo limpio para publicar los PDFs desde cero.")


if __name__ == "__main__":
    main()
