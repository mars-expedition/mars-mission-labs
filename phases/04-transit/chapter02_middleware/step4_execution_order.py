import asyncio
import time

from agent_framework import AgentContext, ChatContext, FunctionInvocationContext

from mission_control import create_mission_control, get_telemetry


async def log_turn(context: AgentContext, call_next) -> None:
    print(f"[AGENTE] Entra: {context.messages[-1].text}")
    start = time.perf_counter()

    await call_next()

    elapsed = time.perf_counter() - start
    print(f"[AGENTE] Sale en {elapsed:.2f} s: {context.result.text}")


async def log_tool_call(context: FunctionInvocationContext, call_next) -> None:
    print(f"[TOOL] Llama a {context.function.name} con {context.arguments}")

    await call_next()

    print(f"[TOOL] Devuelve: {context.result[0].text}")


async def log_model_call(context: ChatContext, call_next) -> None:
    print(f"[CHAT] Llamada al modelo con {len(context.messages)} mensajes")

    await call_next()

    print(f"[CHAT] El modelo terminó con: {context.result.finish_reason}")


async def main() -> None:
    mission_control = create_mission_control(
        middleware=[log_turn, log_tool_call, log_model_call],  # agente, función y chat
        tools=[get_telemetry],
    )

    await mission_control.run("¿Cómo está la propulsión? Consulta la telemetría.")


if __name__ == "__main__":
    asyncio.run(main())