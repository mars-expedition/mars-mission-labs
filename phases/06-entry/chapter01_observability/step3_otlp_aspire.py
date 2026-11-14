import asyncio

from agent_framework.observability import configure_otel_providers, get_tracer
from opentelemetry.trace import SpanKind
from opentelemetry.trace.span import format_trace_id

from mission_control import create_mission_control


async def main() -> None:
    configure_otel_providers()  # con OTEL_EXPORTER_OTLP_ENDPOINT en el .env, también exporta por OTLP

    with get_tracer().start_as_current_span(
        "Scenario: Telemetria via Aspire", kind=SpanKind.CLIENT
    ) as span:
        print(f"Trace ID: {format_trace_id(span.get_span_context().trace_id)}")

        mission_control = create_mission_control()
        response = await mission_control.run("¿Cómo está la propulsión? Consulta la telemetría.")
        print(f"CONTROL: {response.text}")


if __name__ == "__main__":
    asyncio.run(main())
