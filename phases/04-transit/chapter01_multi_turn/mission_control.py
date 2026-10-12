import os

from dotenv import load_dotenv
from agent_framework import Agent
from agent_framework.openai import OpenAIChatCompletionClient

load_dotenv()  # carga las variables del .env (lo busca subiendo de carpeta)

INSTRUCTIONS = (
    "Eres el Control de Misión de una expedición a Marte "
    "y das informes técnicos a la tripulación. Usa terminología espacial. "
    "Responde siempre en una o dos líneas. "
    "Si no tienes un dato, dilo; no lo inventes."  # evita que adivine lo que no sabe
)


def create_mission_control() -> Agent:
    client = OpenAIChatCompletionClient(
        model=os.getenv("AZURE_OPENAI_CHAT_COMPLETION_MODEL"),  # nombre de tu implementación
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),  # dirección de tu recurso de Azure OpenAI
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),  # clave de API
    )
    return Agent(
        client=client,
        name="MissionControl",
        instructions=INSTRUCTIONS
    )  # crea el agente con el cliente