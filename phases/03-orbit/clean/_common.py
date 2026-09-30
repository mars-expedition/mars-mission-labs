from __future__ import annotations

import argparse
import os
from pathlib import Path

try:
    from dotenv import load_dotenv as _load_dotenv
except ModuleNotFoundError:
    _load_dotenv = None


PHASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PHASE_DIR / "data"


def load_phase_env() -> None:
    load_env_file(PHASE_DIR / ".env")
    load_env_file(PHASE_DIR / ".env.local")


def load_env_file(path: Path) -> None:
    if _load_dotenv is not None:
        _load_dotenv(path)
        return

    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "si", "sí"}


def add_yes_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Ejecuta sin pedir confirmacion interactiva.",
    )


def require_env(*names: str) -> dict[str, str]:
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "Faltan variables de entorno: "
            + ", ".join(missing)
            + f". Revisa {PHASE_DIR / '.env'}."
        )
    return {name: os.environ[name] for name in names}


def confirm(message: str, *, yes: bool = False) -> bool:
    if yes or truthy(os.getenv("CLEAN_CONFIRM"), default=False):
        return True

    print(message)
    answer = input("Escribe 'delete' para continuar: ").strip().lower()
    return answer == "delete"


def print_header(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def search_url(endpoint: str, api_version: str, path: str) -> str:
    separator = "&" if "?" in path else "?"
    return f"{endpoint.rstrip('/')}{path}{separator}api-version={api_version}"


def search_resource_path(collection: str, name: str) -> str:
    return f"/{collection}('{name}')"


def create_search_admin_client() -> tuple[httpx.Client, str, str]:
    import httpx
    from azure.identity import DefaultAzureCredential

    env = require_env("AZURE_SEARCH_ENDPOINT", "AZURE_SEARCH_INDEX")
    endpoint = env["AZURE_SEARCH_ENDPOINT"].rstrip("/")
    api_version = os.getenv("AZURE_SEARCH_API_VERSION", "2025-09-01")
    token = DefaultAzureCredential().get_token("https://search.azure.com/.default").token
    client = httpx.Client(
        timeout=120.0,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    return client, endpoint, api_version


def delete_search_resource(
    client,
    *,
    endpoint: str,
    api_version: str,
    collection: str,
    name: str,
) -> None:
    path = search_resource_path(collection, name)
    response = client.delete(search_url(endpoint, api_version, path))

    if response.status_code == 404:
        print(f"- {collection}/{name}: ya no existe")
        return

    if response.status_code not in {200, 202, 204}:
        raise RuntimeError(
            f"No se pudo eliminar {collection}/{name}. "
            f"HTTP {response.status_code}: {response.text}"
        )

    print(f"- {collection}/{name}: eliminado")
