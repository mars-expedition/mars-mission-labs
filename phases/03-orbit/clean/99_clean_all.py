import argparse
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
STEPS = [
    "01_clean_search_assets.py",
    "02_clean_storage_blobs.py",
    "03_clean_foundry_agent.py",
    "04_clean_local_data.py",
]


def main():
    parser = argparse.ArgumentParser(
        description="Ejecuta toda la limpieza de la demo RAG en orden."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Pasa --yes a cada script de limpieza.",
    )
    parser.add_argument(
        "--delete-container",
        action="store_true",
        help="Pasa --delete-container al paso de Blob Storage.",
    )
    args = parser.parse_args()

    for step in STEPS:
        command = [sys.executable, str(SCRIPT_DIR / step)]
        if args.yes:
            command.append("--yes")
        if step == "02_clean_storage_blobs.py" and args.delete_container:
            command.append("--delete-container")

        print("\n>>>", " ".join(command))
        completed = subprocess.run(command, cwd=SCRIPT_DIR.parent)
        if completed.returncode != 0:
            raise SystemExit(completed.returncode)

    print("\nLimpieza completa. Ya puedes ejecutar el tutorial desde cero.")


if __name__ == "__main__":
    main()
