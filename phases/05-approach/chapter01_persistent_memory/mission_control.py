import os

from dotenv import load_dotenv
from agent_framework import Agent, ContextProvider
from agent_framework.openai import OpenAIChatCompletionClient
from agent_framework.redis import RedisHistoryProvider

load_dotenv()  # carga las variables del .env (lo busca subiendo de carpeta)

INSTRUCTIONS = (
    "Eres el Control de Misión de una expedición a Marte "
    "y das informes técnicos a la tripulación. Usa terminología espacial. "
    "Responde siempre en una o dos líneas. "
    "Si no tienes un dato, dilo; no lo inventes."
)

APPLICATION_ID = "mars-mission-control"  # límite de aislamiento obligatorio para el historial con clave "scoped"


def create_redis_history_provider() -> RedisHistoryProvider:
    return RedisHistoryProvider(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
        application_id=APPLICATION_ID,
        agent_id="mission-control",
    )


def create_mission_control(context_providers: list[ContextProvider] | None = None) -> Agent:
    client = OpenAIChatCompletionClient(
        model=os.getenv("AZURE_OPENAI_CHAT_COMPLETION_MODEL"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    )
    return Agent(
        client=client,
        name="MissionControl",
        instructions=INSTRUCTIONS,
        context_providers=context_providers,  # aquí engancha RedisHistoryProvider, Mem0ContextProvider, etc.
    )
