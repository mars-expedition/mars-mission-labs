import asyncio

from agent_framework.mem0 import Mem0ContextProvider

from mission_control import create_memory, create_mission_control

USER_ID = "comandante-ana-torres"  # en producción sería el id real del usuario


async def main() -> None:
    memory = create_memory()  # AsyncMemory.from_config(...): 100% local
    mem0_provider = Mem0ContextProvider(
        mem0_client=memory,
        user_id=USER_ID,  # con quién se guarda cada hecho nuevo (after_run)
        search_user_id=USER_ID,  # de quién se recuperan hechos al empezar un turno (before_run)
    )

    # "Día 1": sesión nueva, memoria semántica vacía para esta comandante
    print("--- Día 1 ---")
    mission_control = create_mission_control(context_providers=[mem0_provider])
    session = mission_control.create_session()
    for message in (
        "Soy la comandante Ana Torres y mi nave se llama Quilla-7.",
        "Prefiero los reportes en una sola línea, sin rodeos.",
    ):
        print(f"COMANDANTE: {message}")
        response = await mission_control.run(message, session=session)
        print(f"CONTROL: {response.text}")
        print()

    # "Día 5": agente y sesión nuevos (como si el programa se hubiera reiniciado varias veces)
    print("--- Día 5: sesión nueva ---")
    mission_control = create_mission_control(context_providers=[mem0_provider])
    session = mission_control.create_session()
    message = "Dame el reporte de propulsión."
    print(f"COMANDANTE: {message}")
    response = await mission_control.run(message, session=session)
    print(f"CONTROL: {response.text}")


if __name__ == "__main__":
    asyncio.run(main())
