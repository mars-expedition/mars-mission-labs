# Fase 04 · TRANSIT: Sesiones y Middleware

Código de la fase 04 del bootcamp **MISIÓN MARTE**. El agente es el Control de Misión de una
expedición a Marte: aprende a recordar la conversación con sesiones, a mirar cada paso de su
ejecución con middleware y a proteger una maniobra con una autorización guardada en la sesión.

Guía completa, con explicaciones y salidas de ejemplo:
**https://mars-expedition.github.io/mars-mission/phases/04-transit.html**

## Contenido de la carpeta

Cada capítulo tiene un `mission_control.py` con ayudantes (crea el agente y define las tools)
y sus `stepN_*.py`, que es donde está lo que se enseña.

| Capítulo | Step | Qué muestra |
|---|---|---|
| `chapter01_multi_turn` | `step1_without_session.py` | Sin sesión, el agente olvida |
| | `step2_with_session.py` | Con `create_session()` y `run(..., session=session)`, recuerda |
| | `step3_session_history.py` | Qué guardó la sesión: `service_session_id` y los mensajes en `session.state` |
| `chapter02_middleware` | `step1_agent_middleware.py` | Middleware de agente: entrada, salida y tiempo del turno |
| | `step2_function_middleware.py` | Middleware de función: qué tool pidió el modelo y qué devolvió |
| | `step3_chat_middleware.py` | Middleware de chat: el modelo se llama dos veces en un turno |
| | `step4_execution_order.py` | Los tres juntos: capas de cebolla |
| `chapter03_session_authorization` | `step1_without_authorization.py` | El problema: cualquiera ejecuta la maniobra TCM-3 |
| | `step2_with_authorization.py` | La solución: un middleware de función bloquea la maniobra hasta verificar el código, y la autorización se guarda en la sesión |

TCM = Trajectory Correction Maneuver (maniobra de corrección de trayectoria). La telemetría,
el código de la comandante y las maniobras son simulados.

## Requisitos

- [uv](https://docs.astral.sh/uv/) (instala Python 3.12 o superior y las dependencias por ti).
- Un recurso de **Azure OpenAI** con una implementación del modelo `gpt-5-mini` y su clave de API.

## Preparación

Desde esta carpeta (`phases/04-transit`):

```bash
uv sync
cp .env.example .env        # en Windows: Copy-Item .env.example .env
```

Completa el `.env` con tus datos. El endpoint va **sin** `/openai/v1` al final:

```bash
AZURE_OPENAI_ENDPOINT=https://<recurso>.openai.azure.com/
AZURE_OPENAI_API_KEY=<tu-clave>
AZURE_OPENAI_CHAT_COMPLETION_MODEL=<nombre-de-tu-implementacion>
```

El `.env` tiene tu clave: no lo subas al repositorio (ya está en `.gitignore`).

## Cómo ejecutar

Desde esta carpeta, cada step se corre así:

```bash
uv run chapter01_multi_turn/step1_without_session.py
```
