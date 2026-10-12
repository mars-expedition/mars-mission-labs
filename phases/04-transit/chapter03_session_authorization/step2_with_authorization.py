import asyncio

from agent_framework import FunctionInvocationContext

from mission_control import create_mission_control, execute_maneuver, verify_commander_code


async def require_authorization(context: FunctionInvocationContext, call_next) -> None:
    state = context.session.state  # datos de esta conversación: duran entre turnos
    print(f"[TOOL] Llama a {context.function.name} con {context.arguments}")  # qué tool pidió el modelo y con qué datos

    if context.function.name == "execute_maneuver" and not state.get("authorized"):
        print("[AUTH] Maniobra bloqueada: la sesión no está autorizada")
        context.result = "BLOQUEADO: la comandante debe dar su código de autorización primero"  # lo que recibe el modelo
        print(f"[TOOL] No se ejecuta; el modelo recibe: {context.result}")
        return  # sin call_next(): la maniobra no se ejecuta

    await call_next()  # deja pasar la ejecución: aquí se ejecuta la tool

    if context.function.name == "verify_commander_code" and context.result[0].text == "VALID":
        state["authorized"] = True  # la autorización queda guardada en la sesión
        print("[AUTH] Sesión autorizada")
    print(f"[TOOL] Devuelve: {context.result[0].text}")  # lo que devolvió la tool al modelo


async def main() -> None:
    mission_control = create_mission_control(
        middleware=[require_authorization],
        tools=[verify_commander_code, execute_maneuver],
    )
    session = mission_control.create_session()

    # TCM = Trajectory Correction Maneuver (maniobra de corrección de trayectoria):
    # encendido corto de motores para corregir el rumbo hacia Marte; el número indica el orden
    for message in (
        "Ejecuta la maniobra TCM-3.",
        "Mi código de autorización es ORION-4421.",
        "Ejecuta también la maniobra TCM-4.",
    ):  # tres turnos de la comandante, en la misma sesión
        print(f"COMANDANTE: {message}")
        response = await mission_control.run(message, session=session)
        print(f"CONTROL: {response.text}")
        print()

    print("--- Otra conversación ---")
    other_session = mission_control.create_session()  # sesión nueva: empieza sin autorización
    message = "Ejecuta la maniobra TCM-3."
    print(f"TRIPULANTE: {message}")
    response = await mission_control.run(message, session=other_session)
    print(f"CONTROL: {response.text}")


if __name__ == "__main__":
    asyncio.run(main())