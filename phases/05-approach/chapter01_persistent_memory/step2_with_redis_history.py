import asyncio

from mission_control import create_mission_control, create_redis_history_provider

SESSION_ID = "comandante-ana-torres"  # mismo id en cada ejecución -> mismo historial en Redis


async def run_mission_control(label: str, message: str) -> None:
    history_provider = create_redis_history_provider()  # antes del turno carga; después, guarda
    mission_control = create_mission_control(context_providers=[history_provider])
    session = mission_control.create_session(session_id=SESSION_ID)

    print(f"[{label}] {message}")
    response = await mission_control.run(message, session=session)
    print(f"[{label}] CONTROL: {response.text}")


async def main() -> None:
    await run_mission_control("Esta ejecución", "Soy la comandante Ana Torres y mi nave se llama Quilla-7.")


if __name__ == "__main__":
    asyncio.run(main())
