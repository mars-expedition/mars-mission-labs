import os
import json
import re
import hashlib
from pypdf import PdfReader
import tiktoken
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from agent_framework.openai import OpenAIEmbeddingClient

# 1. Cargamos las variables de entorno
load_dotenv()

DATA_DIR = "data"
METADATA_FILE = os.path.join(DATA_DIR, "metadata.json")
OUTPUT_FILE = os.path.join(DATA_DIR, "chunks_embedded.json")

AZURE_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
EMBEDDING_MODEL = os.environ["AZURE_OPENAI_EMBEDDING_MODEL"]

credential = DefaultAzureCredential()

embedding_client = OpenAIEmbeddingClient(
    model=EMBEDDING_MODEL,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
    credential=credential,
)

# --- Configuración de Chunking (igual a demo_rag.py) ---
encoding = tiktoken.get_encoding("cl100k_base")
CHUNK_TOKENS = 700
CHUNK_OVERLAP = 100

def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def split_tokens(text: str, chunk_size: int, overlap: int):
    token_ids = encoding.encode(text)
    if not token_ids:
        return []
    
    chunks_text = []
    step = chunk_size - overlap
    for start in range(0, len(token_ids), step):
        chunk_ids = token_ids[start : start + chunk_size]
        if not chunk_ids:
            break
        chunks_text.append(encoding.decode(chunk_ids))
        if start + chunk_size >= len(token_ids):
            break
    return chunks_text

# --- Lógica Principal ---
async def main():
    print("--- Procesando PDFs y Generando Embeddings ---")
    
    # Cargamos la metadata descargada en el paso 01
    if not os.path.exists(METADATA_FILE):
        print("No se encontró metadata.json. Ejecuta primero 01_download_data.py")
        return
        
    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        downloaded_files = json.load(f)
        
    chunks = []
    
    for document in downloaded_files:
        filepath = os.path.join(DATA_DIR, document["filename"])
        if not os.path.exists(filepath):
            continue
            
        print(f"\nProcesando: {document['title']}")
        reader = PdfReader(filepath)
        
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if not text:
                continue
                
            page_text = clean_text(text)
            if len(page_text) < 80:
                continue
                
            page_chunks = split_tokens(page_text, CHUNK_TOKENS, CHUNK_OVERLAP)
            
            for chunk_index, chunk_text in enumerate(page_chunks, start=1):
                clean_chunk = clean_text(chunk_text)
                
                # Generamos una ID estable única para Azure Search
                stable_key = f"{document['filename']}|{page_num}|{chunk_index}|{clean_chunk[:80]}"
                chunk_id = hashlib.sha1(stable_key.encode("utf-8")).hexdigest()
                
                # Generar Vector (Embedding)
                embedding_response = await embedding_client.get_embeddings(values=[clean_chunk])
                vector = embedding_response[0].vector
                
                # Guardar el fragmento con metadata rica
                chunks.append({
                    "id": chunk_id,
                    "title": document["title"],
                    "content": clean_chunk,
                    "source_url": document["url"],
                    "page_number": str(page_num),
                    "category": document["category"],
                    "mission": document["mission"],
                    "content_vector": vector
                })
                print(".", end="", flush=True)
                
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
        
    print(f"\n\n¡Procesamiento completado! Se generaron {len(chunks)} fragmentos vectorizados.")
    print(f"Resultados guardados en: {OUTPUT_FILE}")
    print("Siguiente paso -> Ejecuta '03_setup_search_index.py'")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
