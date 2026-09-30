import os
import json
import httpx
from pathlib import Path
from dotenv import load_dotenv

# 1. Definimos la carpeta donde guardaremos los PDFs de prueba.
SCRIPT_DIR = Path(__file__).resolve().parent
PHASE_DIR = SCRIPT_DIR.parent
load_dotenv(PHASE_DIR / ".env")

DATA_DIR = PHASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 2. Definimos la lista robusta de documentos de misiones a Marte (igual que en demo_rag.py)
MARS_DOCUMENTS = [
    {
        "title": "Mars 2020 Perseverance Launch Press Kit",
        "filename": "mars-2020-launch-press-kit.pdf",
        "url": (
            "https://www.jpl.nasa.gov/news/press_kits/"
            "mars_2020/download/mars_2020_launch_press_kit.pdf"
        ),
        "category": "robotic-mission",
        "mission": "Perseverance",
    },
    {
        "title": "Mars 2020 Perseverance Landing Press Kit",
        "filename": "mars-2020-landing-press-kit.pdf",
        "url": (
            "https://www.jpl.nasa.gov/news/press_kits/"
            "mars_2020/download/mars_2020_landing_press_kit.pdf"
        ),
        "category": "robotic-mission",
        "mission": "Perseverance",
    },
    {
        "title": "Mars Science Laboratory Curiosity Landing Press Kit",
        "filename": "curiosity-landing-press-kit.pdf",
        "url": (
            "https://www.jpl.nasa.gov/news/press_kits/"
            "MSLLanding.pdf"
        ),
        "category": "robotic-mission",
        "mission": "Curiosity",
    },
    {
        "title": "Mars Reconnaissance Orbiter Launch Press Kit",
        "filename": "mro-launch-press-kit.pdf",
        "url": (
            "https://www.jpl.nasa.gov/news/press_kits/"
            "mro-launch.pdf"
        ),
        "category": "robotic-mission",
        "mission": "Mars Reconnaissance Orbiter",
    },
    {
        "title": "MAVEN Press Kit",
        "filename": "maven-press-kit.pdf",
        "url": (
            "https://www.nasa.gov/wp-content/uploads/"
            "2015/03/maven_presskit_final2.pdf"
        ),
        "category": "robotic-mission",
        "mission": "MAVEN",
    },
    {
        "title": "Mars InSight Landing Press Kit",
        "filename": "insight-landing-press-kit.pdf",
        "url": (
            "https://www.jpl.nasa.gov/news/press_kits/"
            "insight/landing/download/"
            "mars_insight_landing_presskit.pdf"
        ),
        "category": "robotic-mission",
        "mission": "InSight",
    },
    {
        "title": "Phoenix Mars Lander Launch Press Kit",
        "filename": "phoenix-launch-press-kit.pdf",
        "url": (
            "https://www.jpl.nasa.gov/news/press_kits/"
            "phoenix-launch-presskit.pdf"
        ),
        "category": "robotic-mission",
        "mission": "Phoenix",
    }
]

print(f"--- Iniciando descarga de documentos en '{DATA_DIR}/' ---")

# 3. Descargamos el contenido usando httpx (más robusto) y guardamos metadata
headers = {"User-Agent": "azure-rag-agent-framework-demo"}
downloaded_metadata = []

with httpx.Client(follow_redirects=True, timeout=180.0, headers=headers) as client:
    for document in MARS_DOCUMENTS:
        local_path = DATA_DIR / document["filename"]
        
        if not local_path.exists():
            print(f"Descargando: {document['title']}...")
            response = client.get(document["url"])
            response.raise_for_status()
            
            content_type = response.headers.get("content-type", "").lower()
            if not response.content.startswith(b"%PDF") and "application/pdf" not in content_type:
                print(f"[ERROR] La descarga de '{document['title']}' no parece ser un PDF.")
                continue
                
            local_path.write_bytes(response.content)
        else:
            print(f"[SKIP] El archivo '{document['filename']}' ya existe.")
            
        downloaded_metadata.append(document)

# 4. Guardamos la metadata para el siguiente script (02_prepare_and_embed.py)
metadata_path = DATA_DIR / "metadata.json"
with open(metadata_path, "w", encoding="utf-8") as f:
    json.dump(downloaded_metadata, f, indent=2, ensure_ascii=False)

print(f"\n¡Descarga completada! {len(downloaded_metadata)} documentos listos.")
print(f"Metadata guardada en: {metadata_path}")
print("Siguiente paso -> Ejecuta '02_prepare_and_embed.py'")
