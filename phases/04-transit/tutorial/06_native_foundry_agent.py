import os
import sys
import time
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    PromptAgentDefinition,
    PromptAgentDefinitionTextOptions,
    AzureAISearchTool,
    AzureAISearchToolResource,
    AISearchIndexResource,
    AzureAISearchQueryType,
    TextResponseFormatJsonSchema,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Cargar variables de entorno del archivo .env principal
load_dotenv()

PROJECT_ENDPOINT = os.getenv("FOUNDRY_PROJECT_ENDPOINT") or os.getenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT")
MODEL_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_CHAT_MODEL")
SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")
AGENT_NAME = os.getenv("FOUNDRY_AGENT_NAME", "marsrag-native-agent")
TOP_K = int(os.getenv("FOUNDRY_AGENT_TOP_K", "3"))
FOUNDRY_QUERY_TYPE = os.getenv("FOUNDRY_AGENT_QUERY_TYPE", "semantic")

AGENT_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "answer": {
            "type": "string",
            "description": "Respuesta final en español, sustentada solo en la evidencia recuperada.",
        },
        "chunks": {
            "type": "array",
            "description": "Fragmentos recuperados y usados para responder.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Texto literal o extracto relevante del fragmento usado como evidencia.",
                    },
                    "score": {
                        "type": "number",
                        "description": "Score de recuperación si está disponible; usa 0 si no está disponible.",
                    },
                    "metadata": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Título o nombre del documento fuente; vacío si no está disponible.",
                            },
                            "source": {
                                "type": "string",
                                "description": "URL o identificador de fuente; vacío si no está disponible.",
                            },
                            "page": {
                                "type": "string",
                                "description": "Página del documento fuente; vacío si no está disponible.",
                            },
                        },
                        "required": ["title", "source", "page"],
                    },
                },
                "required": ["content", "score", "metadata"],
            },
        },
    },
    "required": ["answer", "chunks"],
}

if not PROJECT_ENDPOINT:
    raise ValueError("El Endpoint del proyecto de Foundry no se encontró en el archivo .env.")

print(f"Conectando al Proyecto de Foundry en: {PROJECT_ENDPOINT}")

# 1. Autenticación y Cliente del Proyecto
credential = DefaultAzureCredential()
project_client = AIProjectClient(
    endpoint=PROJECT_ENDPOINT,
    credential=credential,
)

with project_client:
    # 2. Buscar la conexión de Azure AI Search dentro del Proyecto
    print("Buscando conexiones de Azure AI Search en el proyecto...")
    connections = project_client.connections.list()
    
    search_connection_id = None
    for conn in connections:
        if "search" in conn.name.lower() or getattr(conn, "connection_type", "") == "azure_ai_search":
            search_connection_id = conn.id
            print(f"Conexion encontrada: {conn.name} ({conn.id})")
            break
            
    if not search_connection_id:
        raise ValueError("No se encontró ninguna conexión a Azure AI Search en el Proyecto. ¡Asegúrate de haberla agregado desde la interfaz de Foundry!")

    # 3. Crear la Herramienta (Tool) apuntando a nuestro índice
    print(f"Configurando Azure AI Search Tool para el índice '{SEARCH_INDEX}'...")
    ai_search_tool = AzureAISearchTool(
        azure_ai_search=AzureAISearchToolResource(indexes=[
            AISearchIndexResource(
                project_connection_id=search_connection_id,
                index_name=SEARCH_INDEX,
                query_type=FOUNDRY_QUERY_TYPE,
                top_k=TOP_K,
            )
        ])
    )

    # 4. Crear el Agente usando la nueva API v2 (create_version)
    print("Creando una nueva versión del Agente nativo en Foundry...")
    instrucciones = """
    Eres un asistente RAG especializado en documentos de misiones a Marte de la NASA.
    Utiliza siempre tu herramienta de búsqueda antes de responder.
    Responde únicamente con evidencia recuperada desde la base documental.
    Si no encuentras evidencia suficiente, indícalo claramente y devuelve chunks como una lista vacía.

    Debes devolver exclusivamente un objeto JSON válido con esta forma:
    {
      "answer": "respuesta final en español",
      "chunks": [
        {
          "content": "fragmento literal o extracto usado",
          "score": 0,
          "metadata": {
            "title": "título del documento",
            "source": "url o identificador de fuente",
            "page": "página"
          }
        }
      ]
    }

    No incluyas Markdown fuera del JSON. No agregues texto antes ni después del JSON.
    Cada elemento de chunks debe corresponder a una evidencia recuperada y usada para la respuesta.
    Si algún campo de metadata no está disponible en la herramienta, usa una cadena vacía.
    """
    
    agent = project_client.agents.create_version(
        agent_name=AGENT_NAME,
        definition=PromptAgentDefinition(
            model=MODEL_DEPLOYMENT_NAME,
            instructions=instrucciones,
            temperature=0,
            tool_choice="required",
            tools=[ai_search_tool],
            text=PromptAgentDefinitionTextOptions(
                format=TextResponseFormatJsonSchema(
                    name="rag_answer_with_chunks",
                    description="Respuesta RAG con fragmentos recuperados y metadata de fuente.",
                    schema=AGENT_RESPONSE_SCHEMA,
                    strict=True,
                )
            ),
        )
    )
    print(f"Agente creado exitosamente (Nombre: {agent.name}, Version: {agent.version})")
    print("\n¡Ya puedes ir a la pestaña 'Agents' en Azure AI Foundry y ver tu agente con la base de datos enlazada!")

    # 5. Prueba opcional usando el cliente de OpenAI integrado en el SDK (Responses API v2)
    print("\n--- Iniciando prueba de conversación ---")
    openai_client = project_client.get_openai_client()
    conversation = openai_client.conversations.create()
    pregunta = "¿Qué instrumento del rover Curiosity utiliza un láser?"
    
    print(f"Usuario: {pregunta}")
    
    response = openai_client.responses.create(
        conversation=conversation.id,
        input=pregunta,
        extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}}
    )
    
    print(f"Agente: {response.output_text}")
    
    # IMPORTANTE: Si quieres conservar el agente en el portal, deja comentada la siguiente línea.
    # project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
