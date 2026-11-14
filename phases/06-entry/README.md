# Fase 06 · ENTRY: Observabilidad y Evaluación

Código de la fase 06 del bootcamp **MISIÓN MARTE**. El agente sigue siendo el Control de Misión
de una expedición a Marte: instrumenta sus turnos con OpenTelemetry (el framework ya viene
instrumentado, solo se configura a dónde van las trazas) y evalúa la calidad de sus respuestas
con Azure AI Evaluation.

Guía completa, con explicaciones y salidas de ejemplo:
**https://mars-expedition.github.io/mars-mission/phases/06-entry.html**

## Contenido de la carpeta

Cada capítulo tiene un `mission_control.py` con ayudantes y sus `stepN_*.py`, que es donde está
lo que se enseña.

| Capítulo | Step | Qué muestra |
|---|---|---|
| `chapter01_observability` | `step1_console_exporter.py` | `configure_otel_providers()` con exportador de consola: ver las trazas sin ninguna infraestructura |
| | `step2_sensitive_data.py` | `enable_sensitive_data=True`: el contenido real de prompts, respuestas y argumentos de tools aparece en los spans |
| | `step3_otlp_aspire.py` | Mismo código que `step1`, pero con `OTEL_EXPORTER_OTLP_*` apuntando al Aspire Dashboard (con Docker) o a un Tempo de Grafana Cloud por OTLP/HTTP (sin Docker) |
| `chapter02_evaluation` | `step1_f1_score.py` | `F1ScoreEvaluator`: evaluación sin modelo, 100% local |
| | `step2_relevance_and_coherence.py` | `RelevanceEvaluator` y `CoherenceEvaluator`: evaluación con un modelo como juez |
| | `step3_batch_evaluate.py` | `evaluate()` sobre un dataset JSONL (`data.jsonl`), con métricas agregadas y detalle por fila |

La telemetría de la nave sigue siendo simulada: lo real aquí es la instrumentación y la
evaluación.

## Requisitos

- [uv](https://docs.astral.sh/uv/) (instala Python 3.12 o superior y las dependencias por ti).
- Un recurso de **Azure OpenAI** con una implementación del modelo `gpt-5-mini` y su clave de API.
- **Docker** corriendo es opcional: solo lo necesitas para `step3_otlp_aspire.py` si eliges la
  opción del Aspire Dashboard. La alternativa sin Docker (un Tempo de Grafana Cloud) no lo
  necesita; todo lo demás corre sin Docker.

## Preparación

Desde esta carpeta (`phases/06-entry`):

```bash
uv sync
cp .env.example .env        # en Windows: Copy-Item .env.example .env
```

Completa el `.env` con tus datos. El endpoint va **sin** `/openai/v1` al final:

```bash
AZURE_OPENAI_ENDPOINT=https://<recurso>.openai.azure.com/
AZURE_OPENAI_API_KEY=<tu-clave>
AZURE_OPENAI_CHAT_COMPLETION_MODEL=<nombre-de-tu-implementacion>
ENABLE_CONSOLE_EXPORTERS=true
```

El `.env` tiene tu clave: no lo subas al repositorio (ya está en `.gitignore`).

Para `step3_otlp_aspire.py` tienes dos opciones, ambas solo cambiando variables de entorno (el
script no cambia):

**Opción 1 — Aspire Dashboard (con Docker):** levanta el contenedor y descomenta
`OTEL_EXPORTER_OTLP_ENDPOINT` en tu `.env`:

```bash
docker run -d --name mars-aspire -p 18888:18888 -p 4317:18889 mcr.microsoft.com/dotnet/aspire-dashboard:latest
```

Luego abre <http://localhost:18888> para ver las trazas.

**Opción 2 — Tempo de Grafana Cloud (sin Docker):** crea una cuenta gratis, entra a
**Connections → OpenTelemetry** en tu stack y descomenta/completa en tu `.env`:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-<region>.grafana.net/otlp
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <tu-token-en-base64>
```

Grafana Cloud solo acepta OTLP por HTTP, no por gRPC; por eso el `OTEL_EXPORTER_OTLP_PROTOCOL`.
Luego busca la traza por su Trace ID en **Explore** con el datasource de Tempo.

## Cómo ejecutar

Desde esta carpeta, cada step se corre así:

```bash
uv run chapter01_observability/step1_console_exporter.py
uv run chapter02_evaluation/step1_f1_score.py
```
