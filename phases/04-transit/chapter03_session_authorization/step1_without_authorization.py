import asyncio

from mission_control import create_mission_control, execute_maneuver, verify_commander_code


async def main() -> None:
    mission_control = create_mission_control(tools=[verify_commander_code, execute_maneuver])
    session = mission_control.create_session()

    # TCM = Trajectory Correction Maneuver (maniobra de corrección de trayectoria):
    # encendido corto de motores para corregir el rumbo hacia Marte; el número indica el orden
    response = await mission_control.run("Ejecuta la maniobra TCM-3.", session=session)
    print(f"CONTROL: {response.text}")


if __name__ == "__main__":
    asyncio.run(main())