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

TELEMETRY = {
    "propulsion": "Tanques al 82%, motores principales nominales",
    "energia": "Baterías al 91%, paneles solares generando 12 kW",
    "soporte_vital": "O2 21%, CO2 400 ppm, presión de cabina nominal",
}


@tool  # convierte la función en una tool que el modelo puede pedir
def get_telemetry(
    system: Annotated[str, "Sistema a consultar: propulsion, energia o soporte_vital"],  # descripción del parámetro para el modelo
) -> str:
    """Devuelve la telemetría actual de un sistema de la nave."""
    return TELEMETRY.get(system, "Sistema desconocido")  # dato simulado


def create_mission_control(middleware=None, tools=None) -> Agent:
    client = OpenAIChatCompletionClient(
        model=os.getenv("AZURE_OPENAI_CHAT_COMPLETION_MODEL"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    )
    return Agent(
        client=client,
        name="MissionControl",
        instructions=INSTRUCTIONS,
        middleware=middleware,  # middleware del agente: corre en cada run (None = ninguno)
        tools=tools,  # tools que el modelo puede pedir (None = ninguna)
    )