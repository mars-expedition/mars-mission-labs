import asyncio

from agent_framework.observability import configure_otel_providers, get_tracer
from opentelemetry.trace import SpanKind
from opentelemetry.trace.span import format_trace_id

from mission_control import create_mission_control


async def main() -> None:
    # Además de leer el .env, forzamos datos sensibles y consola por si no están en el entorno
    configure_otel_providers(enable_sensitive_data=True, enable_console_exporters=True)

    with get_tracer().start_as_current_span(
        "Scenario: Guiado con datos sensibles", kind=SpanKind.CLIENT
    ) as span:
        print(f"Trace ID: {format_trace_id(span.get_span_context().trace_id)}")

        mission_control = create_mission_control()
        response = await mission_control.run("¿Cómo está el guiado durante la entrada? Consulta el piloto automático.")
        print(f"CONTROL: {response.text}")


if __name__ == "__main__":
    asyncio.run(main())
