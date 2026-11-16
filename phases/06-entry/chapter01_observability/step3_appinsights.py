import asyncio

from agent_framework.observability import enable_instrumentation, get_tracer
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.trace import SpanKind
from opentelemetry.trace.span import format_trace_id

from mission_control import create_mission_control


async def main() -> None:
    # Application Insights no habla OTLP: usa su propio SDK, que configura el
    # TracerProvider global leyendo APPLICATIONINSIGHTS_CONNECTION_STRING del .env.
    # Agent Framework no sabe ni le importa quién configuró el provider: sus
    # spans se adjuntan al que esté activo.
    #
    # sampling_ratio=1.0 fuerza "siempre capturar". El sampler adaptativo por defecto de
    # Application Insights estima una tasa de spans/segundo para decidir qué porcentaje
    # capturar, pensado para un servicio corriendo sin parar; en un script de una sola
    # corrida como este, esa estimación arranca en casi cero y puede descartar tu única
    # traza sin avisarte.
    configure_azure_monitor(sampling_ratio=1.0)

    # enable_instrumentation() releé ENABLE_SENSITIVE_DATA del entorno en este momento.
    # Hace falta porque el import de arriba (`agent_framework.observability`) ya fijó su
    # valor interno la primera vez que Python cargó ese módulo —antes de que
    # `from mission_control import ...`, más abajo, ejecutara load_dotenv() y pusiera
    # ENABLE_SENSITIVE_DATA en el entorno. configure_otel_providers() (Pasos 1 y la Opción 2
    # de este paso) no tiene este problema: releé el entorno solo cada vez que lo llamas.
    enable_instrumentation()

    with get_tracer().start_as_current_span(
        "Scenario: Guiado via Application Insights", kind=SpanKind.CLIENT
    ) as span:
        print(f"Trace ID: {format_trace_id(span.get_span_context().trace_id)}")

        mission_control = create_mission_control()
        response = await mission_control.run("¿Cómo está el guiado durante la entrada? Consulta el piloto automático.")
        print(f"CONTROL: {response.text}")


if __name__ == "__main__":
    asyncio.run(main())
