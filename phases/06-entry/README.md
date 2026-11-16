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
| | `step3_appinsights.py` | Azure Application Insights: no habla OTLP, así que usa `configure_azure_monitor()` del SDK propio de Azure Monitor en vez de `configure_otel_providers()` |
| | `step4_otlp_grafana.py` | Mismo código que `step1`, pero con `OTEL_EXPORTER_OTLP_*` apuntando a un Tempo de Grafana Cloud por OTLP/HTTP |
| `chapter02_evaluation` | `step1_f1_score.py` | `F1ScoreEvaluator`: evaluación sin modelo, 100% local |
| | `step2_relevance_and_coherence.py` | `RelevanceEvaluator` y `CoherenceEvaluator`: evaluación con un modelo como juez |
| | `step3_batch_evaluate.py` | `evaluate()` sobre un dataset JSONL (`data.jsonl`), con métricas agregadas y detalle por fila |

La telemetría de la nave sigue siendo simulada: lo real aquí es la instrumentación y la
evaluación.

## Requisitos

- [uv](https://docs.astral.sh/uv/) (instala Python 3.12 o superior y las dependencias por ti).
- Un recurso de **Azure OpenAI** con una implementación del modelo `gpt-5-mini` y su clave de API.
- Ningún paso de esta fase necesita Docker: `step3_appinsights.py` usa un recurso de Azure, y
  `step4_otlp_grafana.py` un stack gratuito de Grafana Cloud.

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

Dos formas de ver las trazas en una interfaz, además de la consola del Paso 1:

**Opción 1 — Azure Application Insights (sin Docker, sin OTLP):** si ya tienes un recurso de
Application Insights (o App Service/Container Apps con monitoreo de Azure), es la forma más directa
de ver trazas sin Docker. A diferencia de la Opción 2, Application Insights no habla OTLP: trae su
propio SDK (`azure-monitor-opentelemetry`), así que `step3_appinsights.py` usa
`configure_azure_monitor()` en vez de `configure_otel_providers()`. Agent Framework no le importa
quién configuró el `TracerProvider` global: sus spans se adjuntan al que esté activo.

1. Crea un recurso de **Application Insights** en Azure Portal (o usa uno existente).
2. Copia su cadena de conexión en **Overview → Connection String** y descomenta/completa en tu
   `.env`:

```bash
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=<tu-key>;IngestionEndpoint=https://<region>.in.applicationinsights.azure.com/
OTEL_SERVICE_NAME=mars-mission-control
```

3. Ejecuta `uv run chapter01_observability/step3_appinsights.py` y busca el Trace ID en
   **Application Insights → Transaction search** o en **Logs** con una consulta a la tabla
   `dependencies`/`traces`.

Dos detalles importantes de este script:

- El sampler adaptativo que trae Application Insights por defecto estima cuántos spans/segundo
  capturar asumiendo un servicio corriendo sin parar; en un script de una sola corrida como este,
  esa estimación arranca en casi cero y puede descartar tu única traza sin avisarte. Por eso llama a
  `configure_azure_monitor(sampling_ratio=1.0)`, que fuerza capturar siempre.
- `ENABLE_SENSITIVE_DATA` no basta solo: el script también llama a `enable_instrumentation()`.
  `agent_framework.observability` fija el valor de esa variable la primera vez que Python importa
  ese módulo —y en este script eso pasa **antes** de que `from mission_control import ...` ejecute
  `load_dotenv()` y la ponga en el entorno. `enable_instrumentation()` releé la variable al momento
  de llamarlo, ya con el `.env` cargado. `configure_otel_providers()` (el que usa la Opción 2) no
  tiene este problema: ya releé el entorno cada vez que lo llamas, sin necesitar nada extra.

**Opción 2 — Tempo de Grafana Cloud (sin Docker):** crea una cuenta gratis, entra a
**Connections → OpenTelemetry** en tu stack y descomenta/completa en tu `.env`:

```bash
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://otlp-gateway-<region>.grafana.net/otlp/v1/traces
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <tu-token-en-base64>
ENABLE_SENSITIVE_DATA=true
```

Grafana Cloud solo acepta OTLP por HTTP, no por gRPC; por eso el `OTEL_EXPORTER_OTLP_PROTOCOL`.
Usa la variable **específica** de trazas (`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`), no la genérica
`OTEL_EXPORTER_OTLP_ENDPOINT`: la genérica hace que `configure_otel_providers()` también exporte
métricas y logs, que Tempo no acepta (y que inundan tu stack con señales que no pediste). Sin
`ENABLE_SENSITIVE_DATA=true` vas a ver los spans pero no el contenido de prompts/respuestas: esa
variable es independiente de a dónde apunten las trazas. Ejecuta
`uv run chapter01_observability/step4_otlp_grafana.py` y busca la traza por su Trace ID en
**Explore** con el datasource de Tempo.

**¿Ves los spans pero no el contenido, aunque tu consola sí lo muestra?** No es tu `.env`: es una
limitación conocida de Grafana Cloud. Su ingesta de OTLP puede descartar específicamente los
atributos de contenido (`gen_ai.input.messages`, `gen_ai.output.messages`,
`gen_ai.tool.call.arguments`, `gen_ai.tool.call.result`) mientras conserva el resto del span sin
problema, así que ves el modelo, los tokens y el nombre de la tool, pero no el texto. Es distinto
del límite general de Tempo de 2048 bytes por atributo (que trunca, no elimina, y no debería
afectarte con prompts cortos como los de este laboratorio). Si te pasa, Application Insights
(Opción 1) es la forma confiable de ver el contenido completo.

## Cómo ejecutar

Desde esta carpeta, cada step se corre así:

```bash
uv run chapter01_observability/step1_console_exporter.py
uv run chapter02_evaluation/step1_f1_score.py
```
