# Fase 05 · APPROACH: Memoria Persistente

Código de la fase 05 del bootcamp **MISIÓN MARTE**. El agente sigue siendo el Control de Misión
de una expedición a Marte: aprende a que recuerde entre ejecuciones del programa con Redis (o un
archivo local) y a que recuerde hechos aunque la conversación sea otra, con memoria semántica
(Mem0).

Guía completa, con explicaciones y salidas de ejemplo:
**https://mars-expedition.github.io/mars-mission/phases/05-approach.html**

## Contenido de la carpeta

Cada capítulo tiene un `mission_control.py` con ayudantes (crea el agente y la memoria) y sus
`stepN_*.py`, que es donde está lo que se enseña.

| Capítulo | Step | Qué muestra |
|---|---|---|
| `chapter01_persistent_memory` | `step1_without_persistence.py` | `session.state` vive en el proceso: un "Día 2" nuevo olvida el "Día 1" |
| | `step2_with_redis_history.py` | `RedisHistoryProvider`: el historial de la sesión sobrevive a un reinicio, sin guardar nada a mano |
| | `step3_with_file_store.py` | Alternativa sin Docker: `FileSessionStore`, persiste el `AgentSession` completo en un archivo JSON |
| `chapter02_semantic_memory` | `step1_store_and_search.py` | `AsyncMemory` de Mem0 directo: `add()` extrae hechos, `search()` los recupera por similitud |
| | `step2_agent_with_semantic_memory.py` | `Mem0ContextProvider`: el agente recuerda hechos aunque la sesión sea otra |

La telemetría, el nombre de la comandante y la nave son simulados: lo real aquí es la
infraestructura de memoria (Redis, archivo, Mem0).

## Requisitos

- [uv](https://docs.astral.sh/uv/) (instala Python 3.12 o superior y las dependencias por ti).
- Un recurso de **Azure OpenAI** con una implementación del modelo `gpt-5-mini`, una implementación
  de embeddings (p. ej. `text-embedding-3-small`) y su clave de API.
- **Docker** corriendo, para levantar Redis local (capítulo 1, paso con `RedisHistoryProvider`).
  Si no quieres usar Docker, salta directo a `step3_with_file_store.py`.

Esta fase usa dos paquetes del framework todavía en beta (`agent-framework-redis` y
`agent-framework-mem0`), que requieren una versión más reciente de `agent-framework-core` que las
fases anteriores. El `pyproject.toml` ya tiene `prerelease = "allow"`, así que un `uv sync` normal
alcanza.

## Preparación

Desde esta carpeta (`phases/05-approach`):

```bash
uv sync
cp .env.example .env        # en Windows: Copy-Item .env.example .env
```

Completa el `.env` con tus datos. El endpoint va **sin** `/openai/v1` al final:

```bash
AZURE_OPENAI_ENDPOINT=https://<recurso>.openai.azure.com/
AZURE_OPENAI_API_KEY=<tu-clave>
AZURE_OPENAI_CHAT_COMPLETION_MODEL=<nombre-de-tu-implementacion-chat>
AZURE_OPENAI_EMBEDDING_MODEL=<nombre-de-tu-implementacion-embeddings>
REDIS_URL=redis://localhost:6379
```

El `.env` tiene tu clave: no lo subas al repositorio (ya está en `.gitignore`).

Levanta Redis local con un solo comando (necesitas Docker corriendo):

```bash
docker run -d --name mars-redis -p 127.0.0.1:6379:6379 redis:7-alpine
```

## Cómo ejecutar

Desde esta carpeta, cada step se corre así:

```bash
uv run chapter01_persistent_memory/step1_without_persistence.py
```

Para `step2_with_redis_history.py`, corre el script dos veces: primero con el mensaje de ejemplo
tal cual, y luego cambiando el mensaje en `main()` a `"¿Cómo se llama mi nave?"` para ver que la
segunda ejecución (un proceso de Python nuevo) recuerda.
