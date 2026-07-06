# Tutorial: construccion de un agente RAG desde cero

Esta carpeta contiene scripts secuenciales para construir un flujo RAG completo con documentos de misiones a Marte, Azure AI Search y Microsoft Agent Framework.

Ejecuta los comandos desde `phases/04-transit` para que los archivos se generen en la carpeta `data/` de la fase y para reutilizar el `.env` comun.

## Que vas a aprender

1. Descargar documentos PDF y conservar metadata de fuente.
2. Publicar los PDFs en Azure Blob Storage con metadata de negocio.
3. Usar Azure AI Search Text Split Skill para crear chunks.
4. Generar embeddings dentro del indexer con Azure OpenAI Embedding Skill.
5. Crear un indice vectorial en Azure AI Search.
6. Consultar con busqueda hibrida y Semantic Reranker.
7. Convertir la recuperacion en una herramienta de agente.
8. Comparar respuestas con y sin RAG.
9. Conectar un agente nativo de Azure AI Foundry.

## Preparacion

Desde `phases/04-transit`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r tutorial/requirements.txt
Copy-Item .env.example .env
```

Completa `.env` con tus endpoints, deployments, Storage Account, contenedor y nombre de indice. Despues inicia sesion en Azure:

```powershell
az login
az account set --subscription "<SUBSCRIPTION_ID_O_NOMBRE>"
```

El paso de indexacion usa un data source de Azure Blob Storage, un skillset con `Text Split Skill` y `AzureOpenAIEmbeddingSkill`, y un indexer de Azure AI Search.

Permisos recomendados si usas Azure AD en vez de connection string:

- Tu usuario local: `Storage Blob Data Contributor` sobre el Storage Account para subir PDFs en `02_prepare_and_embed.py`.
- Azure AI Search: identidad administrada habilitada y rol `Storage Blob Data Reader` sobre el Storage Account para que el indexer lea los PDFs.
- Azure AI Search: si no usas `AZURE_OPENAI_API_KEY`, rol `Cognitive Services OpenAI User` sobre el recurso de Azure OpenAI para ejecutar el embedding skill.

Ejemplo con Azure CLI para el usuario autenticado:

```powershell
$userObjectId = az ad signed-in-user show --query id -o tsv
az role assignment create `
  --assignee-object-id $userObjectId `
  --assignee-principal-type User `
  --role "Storage Blob Data Contributor" `
  --scope "/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Storage/storageAccounts/<storage-account>"
```

Los permisos RBAC pueden tardar unos minutos en propagarse.

## Orden de ejecucion

```powershell
python tutorial/01_download_data.py
python tutorial/02_prepare_and_embed.py
python tutorial/03_setup_search_index.py
python tutorial/04_agent_with_rag.py
python tutorial/05_agent_comparison.py
python tutorial/06_native_foundry_agent.py
```

## Limpiar y volver a cero

Antes de una presentacion o ensayo puedes dejar la demo como recien creada:

```powershell
python clean/00_show_cleanup_plan.py
python clean/99_clean_all.py --yes
```

La limpieza elimina recursos derivados de la demo, no los servicios base. Debes conservar Azure OpenAI/Foundry deployments, Azure AI Search service, Storage Account y Azure AI Foundry Project.

## Que produce cada paso

- `01_download_data.py`: descarga PDFs y guarda `data/metadata.json`.
- `02_prepare_and_embed.py`: sube los PDFs a Azure Blob Storage y guarda `data/blob_manifest.json`.
- `03_setup_search_index.py`: crea el indice, data source, skillset e indexer para chunking y embeddings nativos en Azure AI Search.
- `04_agent_with_rag.py`: prueba un agente local que usa la recuperacion como herramienta.
- `05_agent_comparison.py`: compara una respuesta con RAG frente a una sin RAG.
- `06_native_foundry_agent.py`: prepara o usa un agente nativo en Azure AI Foundry.

## Requisito para el agente nativo de Foundry

`06_native_foundry_agent.py` necesita que el proyecto de Azure AI Foundry tenga una conexion registrada hacia Azure AI Search. Esta conexion no se crea al ejecutar el indexer.

Desde Azure AI Foundry:

1. Abre el recurso/proyecto configurado en `FOUNDRY_PROJECT_ENDPOINT`.
2. Si estas en la vista general del recurso, haz clic en `Abrir proyecto`.
3. En el detalle del proyecto, entra a la pestana `Recursos conectados`.
4. Haz clic en `Agregar conexion`.
5. Agrega una conexion de tipo `Azure AI Search` o `CognitiveSearch`.
6. Selecciona el Search service donde vive `AZURE_SEARCH_INDEX`.
7. Guarda la conexion y vuelve a ejecutar `python tutorial/06_native_foundry_agent.py`.

Si tienes varias conexiones, puedes fijar una en `.env`:

```dotenv
FOUNDRY_SEARCH_CONNECTION_NAME=<nombre-de-la-conexion>
# o
FOUNDRY_SEARCH_CONNECTION_ID=<id-completo-de-la-conexion>
```

## Buenas practicas para la demo

- Ejecuta primero una pregunta cuya respuesta este claramente en los documentos.
- Muestra los fragmentos recuperados antes de revelar la respuesta final.
- Para comparar rerank, usa `05_agent_comparison.py` o el playground con: `Que mision busca senales de vida antigua en el crater Jezero?`. El prompt usa grounding estricto: sin rerank deberia reconocer falta de evidencia suficiente; con rerank prioriza Mars 2020 Perseverance.
- Usa una pregunta fuera del corpus para demostrar que el agente no debe inventar.
- Si cambias el modelo de embeddings, revisa `AZURE_OPENAI_EMBEDDING_MODEL_NAME`, `EMBEDDING_DIMENSIONS` y recrea el indice.
- Si cambias `AZURE_SEARCH_TEXT_SPLIT_MAX_LENGTH` u `OVERLAP`, vuelve a ejecutar el indexer.
- Con `AZURE_SEARCH_API_VERSION=2025-09-01`, el chunking por caracteres usa el default del Text Split Skill. No se envia la propiedad `unit`; el modo `azureOpenAITokens` requiere una API preview.
- `04_agent_with_rag.py` y `05_agent_comparison.py` usan Microsoft Agent Framework con Responses API. Deja `AZURE_OPENAI_RESPONSES_API_VERSION` vacio salvo que necesites forzar una version compatible con tu endpoint.
- No subas `.env` ni archivos con llaves o endpoints privados.
