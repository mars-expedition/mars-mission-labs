import os

from dotenv import load_dotenv
from agent_framework import Agent, ContextProvider
from agent_framework.openai import OpenAIChatCompletionClient
from mem0 import AsyncMemory

load_dotenv()  # carga las variables del .env (lo busca subiendo de carpeta)

INSTRUCTIONS = (
    "Eres el Control de Misión de una expedición a Marte "
    "y das informes técnicos a la tripulación. Usa terminología espacial. "
    "Responde siempre en una o dos líneas. "
    "Si no tienes un dato, dilo; no lo inventes."
)

CHAT_MODEL = os.getenv("AZURE_OPENAI_CHAT_COMPLETION_MODEL")
EMBEDDING_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL")
AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
API_VERSION = "2024-10-21"


def _azure_config(deployment: str | None) -> dict:
    """Config de un modelo de Azure OpenAI para Mem0 (igual para el de chat y el de embeddings)."""
    return {
        "model": deployment,  # se envía como "model" en cada llamada a Azure OpenAI
        "azure_kwargs": {
            "azure_deployment": deployment,
            "azure_endpoint": AZURE_ENDPOINT,
            "api_key": AZURE_API_KEY,
            "api_version": API_VERSION,
        },
    }


MEM0_CONFIG = {
    "llm": {"provider": "azure_openai", "config": _azure_config(CHAT_MODEL)},
    "embedder": {
        "provider": "azure_openai",
        "config": {**_azure_config(EMBEDDING_MODEL), "embedding_dims": 1536},  # dimensiones de text-embedding-3-small
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "path": "./mem0_db",  # Qdrant embebido en disco: sin servidor, memoria semántica 100% local
            "collection_name": "mars_crew_memory",
            "embedding_model_dims": 1536,  # debe coincidir con las dimensiones del embedder
        },
    },
}


def create_memory() -> AsyncMemory:
    return AsyncMemory.from_config(MEM0_CONFIG)


def create_mission_control(context_providers: list[ContextProvider] | None = None) -> Agent:
    client = OpenAIChatCompletionClient(
        model=CHAT_MODEL,
        azure_endpoint=AZURE_ENDPOINT,
        api_key=AZURE_API_KEY,
    )
    return Agent(
        client=client,
        name="MissionControl",
        instructions=INSTRUCTIONS,
        context_providers=context_providers,
    )
