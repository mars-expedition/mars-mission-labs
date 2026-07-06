import argparse
import shutil

from _common import DATA_DIR, PHASE_DIR, add_yes_arg, confirm, load_phase_env, print_header


def main():
    parser = argparse.ArgumentParser(
        description="Elimina datos locales generados por el tutorial."
    )
    add_yes_arg(parser)
    args = parser.parse_args()

    load_phase_env()

    target = DATA_DIR.resolve()
    phase = PHASE_DIR.resolve()

    print_header("04 - Limpieza de datos locales")
    print("Directorio:", target)

    if target == phase or phase not in target.parents:
        raise RuntimeError(f"Ruta insegura para borrar: {target}")

    if not target.exists():
        print("No existe data/. Nada que limpiar.")
        return

    if not confirm("\nEsta accion eliminara la carpeta local data/.", yes=args.yes):
        print("Cancelado.")
        return

    shutil.rmtree(target)
    print("Datos locales eliminados.")


if __name__ == "__main__":
    main()
