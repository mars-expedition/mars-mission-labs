"""Configuración y carga de variables de entorno para el backend."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Sequence

from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

# Rutas clave del proyecto
BACKEND_DIR = Path(__file__).resolve().parent
DEMO_DIR = BACKEND_DIR.parent
PHASE_DIR = DEMO_DIR.parent

# Cargar variables de entorno prioritarias (.env de la fase)
for env_path in (PHASE_DIR / ".env", DEMO_DIR / ".env", BACKEND_DIR / ".env"):
    if env_path.exists():
        load_dotenv(env_path)
        break


@dataclass(frozen=True)
class Settings:
    """Configuración de Azure OpenAI, Azure AI Search y Azure AI Foundry."""

    # Azure OpenAI
    azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    azure_openai_chat_model: str = (
        os.getenv("AZURE_OPENAI_CHAT_COMPLETION_MODEL")
        or os.getenv("AZURE_OPENAI_CHAT_MODEL")
        or ""
    )
    azure_openai_chat_api_version: str = os.getenv(
        "AZURE_OPENAI_CHAT_COMPLETION_API_VERSION", "2024-02-15-preview"
    )
    azure_openai_embedding_model: str = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL", "")
    azure_openai_embedding_api_version: str = (
        os.getenv("AZURE_OPENAI_EMBEDDING_API_VERSION")
        or os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
    )

    # Azure AI Search
    azure_search_endpoint: str = os.getenv("AZURE_SEARCH_ENDPOINT", "").rstrip("/")
    azure_search_index: str = os.getenv("AZURE_SEARCH_INDEX", "")

    # Azure AI Foundry Native Agent
    foundry_project_endpoint: str = (
        os.getenv("FOUNDRY_PROJECT_ENDPOINT")
        or os.getenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT")
        or ""
    )
    foundry_agent_name: str = os.getenv("FOUNDRY_AGENT_NAME", "marsrag-native-agent")

    # CORS
    cors_origins: Sequence[str] = ("http://localhost:3000",)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna una instancia cacheada e inmutable de la configuración."""
    return Settings()


@lru_cache(maxsize=1)
def get_azure_credential() -> DefaultAzureCredential:
    """Retorna la credencial compartida de Azure Identity."""
    return DefaultAzureCredential()
