import asyncio

from agent_framework import FunctionInvocationContext

from mission_control import create_mission_control, get_telemetry


async def log_tool_call(context: FunctionInvocationContext, call_next) -> None:
    print(f"[TOOL] Llama a {context.function.name} con {context.arguments}")  # tool y datos que pidió el modelo

    await call_next()  # deja pasar la ejecución: aquí se ejecuta la tool

    print(f"[TOOL] Devuelve: {context.result[0].text}")  # resultado de la tool


async def main() -> None:
    mission_control = create_mission_control(
        middleware=[log_tool_call],  # middleware de función
        tools=[get_telemetry],  # el modelo puede pedir esta tool
    )

    response = await mission_control.run("¿Cómo está la propulsión? Consulta la telemetría.")
    print()
    print(f"CONTROL: {response.text}")


if __name__ == "__main__":
    asyncio.run(main())