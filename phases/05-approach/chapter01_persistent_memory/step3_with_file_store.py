import asyncio

from agent_framework import FileSessionStore

from mission_control import create_mission_control

SESSION_ID = "comandante-ana-torres"
store = FileSessionStore(".sessions")  # un archivo JSON por sesión en phases/05-approach/.sessions/


async def run_mission_control(label: str, message: str) -> None:
    mission_control = create_mission_control()  # sin context_providers: usa InMemoryHistoryProvider por defecto

    session = await store.get(SESSION_ID)  # None la primera vez
    if session is None:
        session = mission_control.create_session(session_id=SESSION_ID)
        print(f"[{label}] Sin memoria previa en el archivo")
    else:
        print(f"[{label}] Sesión recuperada del archivo")

    print(f"[{label}] {message}")
    response = await mission_control.run(message, session=session)
    print(f"[{label}] CONTROL: {response.text}")

    await store.set(SESSION_ID, session)  # persiste todo session.state para la próxima ejecución


async def main() -> None:
    await run_mission_control("Esta ejecución", "Soy la comandante Ana Torres y mi nave se llama Quilla-7.")


if __name__ == "__main__":
    asyncio.run(main())
