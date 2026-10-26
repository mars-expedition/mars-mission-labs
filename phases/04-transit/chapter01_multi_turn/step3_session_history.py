import asyncio

from mission_control import create_mission_control


async def main() -> None:
    mission_control = create_mission_control()
    session = mission_control.create_session()

    await mission_control.run("Soy la comandante Ana Torres y mi nave se llama Quilla-7.", session=session)
    await mission_control.run("¿Cómo se llama mi nave?", session=session)

    print(f"service_session_id: {session.service_session_id}")  # None: Azure no guarda esta conversación; la guarda la sesión, en tu programa
    print()

    messages = session.state["in_memory"]["messages"]  # historial guardado en la sesión, en tu programa
    print(f"Mensajes guardados en la sesión: {len(messages)}")
    for message in messages:
        print(f"  {message.role}: {message.text}")  # quién habló y qué dijo


if __name__ == "__main__":
    asyncio.run(main())