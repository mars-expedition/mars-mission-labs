import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    PromptAgentDefinition,
    PromptAgentDefinitionTextOptions,
    AzureAISearchTool,
    AzureAISearchToolResource,
    AISearchIndexResource,
    TextResponseFormatJsonSchema,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Cargar variables de entorno del archivo .env principal.
SCRIPT_DIR = Path(__file__).resolve().parent
PHASE_DIR = SCRIPT_DIR.parent
load_dotenv(PHASE_DIR / ".env")

PROJECT_ENDPOINT = os.getenv("FOUNDRY_PROJECT_ENDPOINT") or os.getenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT")
MODEL_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_CHAT_MODEL")
SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")
AGENT_NAME = os.getenv("FOUNDRY_AGENT_NAME", "marsrag-native-agent")
SEARCH_CONNECTION_ID = os.getenv("FOUNDRY_SEARCH_CONNECTION_ID") or os.getenv("AZURE_AI_SEARCH_CONNECTION_ID")
SEARCH_CONNECTION_NAME = os.getenv("FOUNDRY_SEARCH_CONNECTION_NAME") or os.getenv("AZURE_AI_SEARCH_CONNECTION_NAME")
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


def connection_dict(connection) -> dict:
    if hasattr(connection, "as_dict"):
        return connection.as_dict()
    return getattr(connection, "__dict__", {})


def connection_name(connection) -> str:
    return str(getattr(connection, "name", None) or connection_dict(connection).get("name") or "")


def connection_id(connection) -> str:
    return str(getattr(connection, "id", None) or connection_dict(connection).get("id") or "")


def connection_type(connection) -> str:
    data = connection_dict(connection)
    return str(
        getattr(connection, "connection_type", None)
        or getattr(connection, "type", None)
        or data.get("connection_type")
        or data.get("type")
        or ""
    )


def connection_target(connection) -> str:
    data = connection_dict(connection)
    metadata = data.get("metadata") or {}
    return str(
        getattr(connection, "target", None)
        or data.get("target")
        or metadata.get("ResourceId")
        or metadata.get("resourceId")
        or ""
    )


def is_search_connection(connection) -> bool:
    searchable_text = " ".join(
        [
            connection_name(connection),
            connection_type(connection),
            connection_target(connection),
        ]
    ).lower()
    return any(
        token in searchable_text
        for token in (
            "cognitivesearch",
            "azure_ai_search",
            "azure ai search",
            "microsoft.search/searchservices",
            "search.windows.net",
        )
    )


def print_connection_summary(connections) -> None:
    if not connections:
        print("No se encontraron conexiones en el proyecto.")
        return

    print("Conexiones disponibles en el proyecto:")
    for connection in connections:
        print(
            "- "
            f"name={connection_name(connection) or '(sin nombre)'} | "
            f"type={connection_type(connection) or '(sin tipo)'} | "
            f"target={connection_target(connection) or '(sin target)'}"
        )


def print_search_connection_help() -> None:
    print("\nNo hay una conexión de Azure AI Search registrada en este proyecto Foundry.")
    print("Crea una conexión una sola vez desde Azure AI Foundry:")
    print("1. Abre tu proyecto en Azure AI Foundry.")
    print("2. Ve a Management center / Connected resources / Connections.")
    print("3. Agrega una conexión de tipo Azure AI Search.")
    print("4. Selecciona el servicio de búsqueda que contiene el índice:")
    print(f"   {SEARCH_INDEX}")
    print("5. Guarda la conexión y vuelve a ejecutar este script.")
    print()
    print("Opcionalmente agrega al .env uno de estos valores:")
    print("FOUNDRY_SEARCH_CONNECTION_NAME=<nombre-de-la-conexion>")
    print("FOUNDRY_SEARCH_CONNECTION_ID=<id-completo-de-la-conexion>")


def find_search_connection_id(project_client) -> str:
    if SEARCH_CONNECTION_ID:
        print("Usando FOUNDRY_SEARCH_CONNECTION_ID desde .env.")
        return SEARCH_CONNECTION_ID

    if SEARCH_CONNECTION_NAME:
        print(f"Buscando conexión por nombre: {SEARCH_CONNECTION_NAME}")
        connection = project_client.connections.get(SEARCH_CONNECTION_NAME)
        print(f"Conexión encontrada: {connection_name(connection)} ({connection_id(connection)})")
        return connection_id(connection)

    try:
        default_search = project_client.connections.get_default("CognitiveSearch")
        print(f"Conexión default de Azure AI Search encontrada: {connection_name(default_search)}")
        return connection_id(default_search)
    except Exception:
        pass

    connections = list(project_client.connections.list())
    search_connections = [connection for connection in connections if is_search_connection(connection)]

    if search_connections:
        connection = search_connections[0]
        print(f"Conexión Azure AI Search encontrada: {connection_name(connection)} ({connection_id(connection)})")
        return connection_id(connection)

    print_connection_summary(connections)
    print_search_connection_help()
    raise SystemExit(2)


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
    search_connection_id = find_search_connection_id(project_client)

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
