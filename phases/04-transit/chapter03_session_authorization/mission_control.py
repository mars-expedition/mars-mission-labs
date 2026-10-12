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

COMMANDER_CODE = "ORION-4421"  # código registrado de la comandante (simplificación de la demo)


@tool
def verify_commander_code(
    code: Annotated[str, "Código de autorización que dio la comandante"],
) -> str:
    """Verifica el código de autorización de la comandante."""
    return "VALID" if code == COMMANDER_CODE else "INVALID"  # compara con el código registrado


# TCM = Trajectory Correction Maneuver (maniobra de corrección de trayectoria):
# encendido corto de motores para corregir el rumbo hacia Marte; el número indica el orden
@tool
def execute_maneuver(
    maneuver: Annotated[str, "Nombre de la maniobra, por ejemplo TCM-3"],
) -> str:
    """Enciende los motores para ejecutar una maniobra de la nave."""
    print(f"[NAVE] Motores encendidos: maniobra {maneuver} ejecutada")  # muestra cuándo se ejecuta de verdad
    return f"Maniobra {maneuver} ejecutada"


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
        middleware=middleware,
        tools=tools,
    )