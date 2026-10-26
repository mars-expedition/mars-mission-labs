import asyncio

from agent_framework import ChatContext

from mission_control import create_mission_control, get_telemetry


async def log_model_call(context: ChatContext, call_next) -> None:
    print(f"[CHAT] Llamada al modelo con {len(context.messages)} mensajes")  # mensajes enviados en esta llamada

    await call_next()  # deja pasar la ejecución: aquí se llama al modelo en Azure

    print(f"[CHAT] El modelo terminó con: {context.result.finish_reason}")  # tool_calls = pide tool; stop = respuesta final


async def main() -> None:
    mission_control = create_mission_control(
        middleware=[log_model_call],  # middleware de chat
        tools=[get_telemetry],
    )

    response = await mission_control.run("¿Cómo está la propulsión? Consulta la telemetría.")
    print()
    print(f"CONTROL: {response.text}")


if __name__ == "__main__":
    asyncio.run(main())