import asyncio

from mission_control import create_mission_control


async def main() -> None:
    mission_control = create_mission_control()
    session = mission_control.create_session()  # guardará el historial de esta conversación

    response = await mission_control.run(
        "Soy la comandante Ana Torres y mi nave se llama Quilla-7.",
        session=session,  # el turno se guarda en la sesión
    )
    print(f"CONTROL: {response.text}")
    print()

    response = await mission_control.run("¿Cómo se llama mi nave?", session=session)  # recibe el turno anterior
    print(f"CONTROL: {response.text}")


if __name__ == "__main__":
    asyncio.run(main())
