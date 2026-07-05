# Tutorial: construccion de un agente RAG desde cero

Esta carpeta contiene scripts secuenciales para construir un flujo RAG completo con documentos de misiones a Marte, Azure AI Search y Microsoft Agent Framework.

Ejecuta los comandos desde `phases/04-transit` para que los archivos se generen en la carpeta `data/` de la fase y para reutilizar el `.env` comun.

## Que vas a aprender

1. Descargar documentos PDF y conservar metadata de fuente.
2. Extraer texto, limpiar contenido y crear chunks.
3. Generar embeddings para cada fragmento.
4. Crear un indice vectorial en Azure AI Search.
5. Consultar con busqueda hibrida y Semantic Reranker.
6. Convertir la recuperacion en una herramienta de agente.
7. Comparar respuestas con y sin RAG.
8. Conectar un agente nativo de Azure AI Foundry.

## Preparacion

Desde `phases/04-transit`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r tutorial/requirements.txt
Copy-Item .env.example .env
```

Completa `.env` con tus endpoints, deployments y nombre de indice. Despues inicia sesion en Azure:

```powershell
az login
az account set --subscription "<SUBSCRIPTION_ID_O_NOMBRE>"
```

## Orden de ejecucion

```powershell
python tutorial/01_download_data.py
python tutorial/02_prepare_and_embed.py
python tutorial/03_setup_search_index.py
python tutorial/04_agent_with_rag.py
python tutorial/05_agent_comparison.py
python tutorial/06_native_foundry_agent.py
```

## Que produce cada paso

- `01_download_data.py`: descarga PDFs y guarda `data/metadata.json`.
- `02_prepare_and_embed.py`: genera chunks vectorizados en `data/chunks_embedded.json`.
- `03_setup_search_index.py`: crea el indice y sube los documentos a Azure AI Search.
- `04_agent_with_rag.py`: prueba un agente local que usa la recuperacion como herramienta.
- `05_agent_comparison.py`: compara una respuesta con RAG frente a una sin RAG.
- `06_native_foundry_agent.py`: prepara o usa un agente nativo en Azure AI Foundry.

## Buenas practicas para la demo

- Ejecuta primero una pregunta cuya respuesta este claramente en los documentos.
- Muestra los fragmentos recuperados antes de revelar la respuesta final.
- Usa una pregunta fuera del corpus para demostrar que el agente no debe inventar.
- Si cambias el modelo de embeddings, revisa `EMBEDDING_DIMENSIONS` y recrea el indice.
- No subas `.env` ni archivos con llaves o endpoints privados.
