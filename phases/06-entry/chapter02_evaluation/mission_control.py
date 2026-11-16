import os
from typing import Annotated

from dotenv import load_dotenv
from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatCompletionClient

load_dotenv()  # carga las variables del .env (lo busca subiendo de carpeta)

INSTRUCTIONS = (
    "Eres el Control de Misión de una expedición a Marte "
    "y das informes técnicos a la tripulación. Usa terminología espacial. "
    "Responde siempre en una o dos líneas. "
    "Si no tienes un dato, dilo; no lo inventes."
)

# Durante la entrada nadie en la Tierra puede intervenir: estos subsistemas deciden solos.
AUTOPILOT_STATUS = {
    "guiado": "Computadora de guiado: trayectoria nominal, desviación de 0.3°, sin correcciones pendientes",
    "secuenciador": "Secuenciador de eventos: próximo evento en T-45s (despliegue de paracaídas), sin bloqueos",
    "monitor_aborto": "Monitor de aborto: todos los parámetros dentro de límites, sin recomendación de abortar",
}


@tool
def get_autopilot_status(
    subsystem: Annotated[str, "Subsistema autónomo a consultar: guiado, secuenciador o monitor_aborto"],
) -> str:
    """Devuelve el estado de un subsistema autónomo de la nave durante la entrada atmosférica."""
    return AUTOPILOT_STATUS.get(subsystem, "Subsistema desconocido")  # dato simulado


def create_mission_control() -> Agent:
    client = OpenAIChatCompletionClient(
        model=os.getenv("AZURE_OPENAI_CHAT_COMPLETION_MODEL"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    )
    return Agent(
        client=client,
        name="MissionControl",
        instructions=INSTRUCTIONS,
        tools=[get_autopilot_status],
    )
