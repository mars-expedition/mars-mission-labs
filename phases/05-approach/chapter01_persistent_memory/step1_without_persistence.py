import asyncio

from mission_control import create_mission_control


async def run_day(label: str, message: str) -> None:
    # cada "día" es una ejecución nueva del programa: agente y sesión desde cero
    mission_control = create_mission_control()
    session = mission_control.create_session()

    print(f"[{label}] {message}")
    response = await mission_control.run(message, session=session)
    print(f"[{label}] CONTROL: {response.text}")
    print()


async def main() -> None:
    await run_day("Día 1", "Soy la comandante Ana Torres y mi nave se llama Quilla-7.")
    await run_day("Día 2", "¿Cómo se llama mi nave?")  # proceso nuevo: no recibe el día anterior


if __name__ == "__main__":
    asyncio.run(main())
