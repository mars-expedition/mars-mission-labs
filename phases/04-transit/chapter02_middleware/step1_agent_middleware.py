import asyncio
import time

from agent_framework import AgentContext

from mission_control import create_mission_control


async def log_turn(context: AgentContext, call_next) -> None:
    print(f"[AGENTE] Entra: {context.messages[-1].text}")  # último mensaje que entra al agente
    start = time.perf_counter()  # marca el tiempo antes de ejecutar

    await call_next()  # deja pasar la ejecución: aquí el agente llama al modelo

    elapsed = time.perf_counter() - start  # tiempo que tardó el turno
    print(f"[AGENTE] Sale en {elapsed:.2f} s: {context.result.text}")  # la respuesta ya existe


async def main() -> None:
    mission_control = create_mission_control(middleware=[log_turn])  # registra el middleware en el agente

    await mission_control.run("Control, solicito el estado general de la misión.")


if __name__ == "__main__":
    asyncio.run(main())