# Fase 04 - Transit: RAG con Azure AI Foundry

Esta fase presenta los beneficios de **RAG (Retrieval-Augmented Generation)** mediante una demo con documentos de misiones a Marte. El objetivo es que una persona pueda ver, paso a paso, como una pregunta se convierte en busqueda, evidencia recuperada y respuesta fundamentada con fuentes.

RAG no entrena de nuevo al modelo. En su lugar, recupera informacion relevante desde una base documental en tiempo de consulta y la entrega como contexto al modelo generativo.

## Que demuestra esta fase

- **Grounding**: las respuestas se apoyan en fragmentos reales del corpus.
- **Trazabilidad**: cada respuesta puede mostrar documentos, paginas y URLs fuente.
- **Actualizacion rapida**: agregar o reemplazar documentos evita reentrenar modelos.
- **Menos alucinaciones**: el agente debe reconocer cuando no hay evidencia suficiente.
- **Comparacion de tecnicas**: busqueda vectorial, busqueda hibrida y Semantic Reranker.
- **Arquitectura extensible**: la recuperacion se expone como herramienta para un agente.

## Arquitectura

```text
PDFs NASA
  -> Azure Blob Storage
  -> Azure AI Search Indexer
  -> Text Split Skill + AzureOpenAIEmbeddingSkill
  -> indice vectorial con chunks proyectados
  -> recuperacion hibrida / rerank
  -> agente local o agente nativo Foundry
  -> respuesta citada en la UI
```

## Contenido de la carpeta

- `demo_rag_azure_agent_framework.ipynb`: notebook narrativo para presentar el pipeline completo.
- `demo_rag.py`: version exportada del notebook, util como referencia de codigo.
- `requirements.txt`: dependencias Python para la fase completa.
- `.env.example`: plantilla de variables de entorno para Azure OpenAI, Azure AI Search y Foundry.
- `tutorial/`: scripts secuenciales para construir el indice y probar agentes RAG desde cero.
- `clean/`: scripts secuenciales para limpiar recursos derivados y repetir la demo desde cero.
- `demo/backend/`: API FastAPI usada por la demo web.
- `demo/app/`: frontend Next.js para explorar documentos, chatear y comparar rerank.
- `data/`: PDFs de referencia para el escenario de misiones a Marte.

## Requisitos previos

- Python 3.10 o superior.
- Node.js 18 o superior y `npm`.
- Azure CLI autenticado con `az login`.
- Recursos de Azure con permisos para:
  - Azure OpenAI o modelos en Azure AI Foundry.
  - Azure AI Search.
  - Azure AI Foundry Project, si usaras el agente nativo.

Roles recomendados para desarrollo local:

- En Azure OpenAI / Foundry Models: `Cognitive Services OpenAI User`.
- En Azure AI Search: `Search Service Contributor`, `Search Index Data Contributor` y `Search Index Data Reader`.
- En Storage Account: `Storage Blob Data Contributor` para tu usuario y `Storage Blob Data Reader` para la identidad administrada de Azure AI Search si usas `ResourceId`.
- En Azure AI Foundry: el proyecto debe tener Azure AI Search agregado en `Recursos conectados` para que el agente nativo pueda usar el indice.

## Configuracion

Desde esta carpeta:

```powershell
cd phases/04-transit
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edita `.env` con tus endpoints, nombres de deployments e indice. Los valores `AZURE_OPENAI_CHAT_MODEL` y `AZURE_OPENAI_EMBEDDING_MODEL` deben ser nombres de deployments, no necesariamente el nombre base del modelo.

Luego autenticate:

```powershell
az login
az account set --subscription "<SUBSCRIPTION_ID_O_NOMBRE>"
```

## Camino recomendado para la demo

1. Abre `demo_rag_azure_agent_framework.ipynb` para explicar el flujo completo.
2. Ejecuta los scripts de `tutorial/` si necesitas reconstruir el indice paso a paso.
3. Levanta el backend FastAPI.
4. Levanta el frontend Next.js.
5. Usa las pantallas de documentos, chat y playground para mostrar beneficios y tecnicas.

### Reconstruir el indice desde scripts

Ejecuta desde `phases/04-transit` para que los datos queden en `data/` y se use el `.env` de la fase:

```powershell
pip install -r tutorial/requirements.txt
python tutorial/01_download_data.py
python tutorial/02_prepare_and_embed.py
python tutorial/03_setup_search_index.py
python tutorial/04_agent_with_rag.py
python tutorial/05_agent_comparison.py
python tutorial/06_native_foundry_agent.py
```

### Conectar Azure AI Search al proyecto Foundry

El script `tutorial/06_native_foundry_agent.py` crea una version del agente nativo de Azure AI Foundry. Antes de ejecutarlo, entra al detalle del proyecto en Azure AI Foundry y registra el Search service como recurso conectado:

1. Abre Azure AI Foundry y entra al proyecto de `FOUNDRY_PROJECT_ENDPOINT`.
2. Haz clic en `Abrir proyecto` si estas en la vista del recurso.
3. En el detalle del proyecto, abre `Recursos conectados`.
4. Selecciona `Agregar conexion`.
5. Elige `Azure AI Search` o `CognitiveSearch`.
6. Selecciona el Search service donde vive `AZURE_SEARCH_INDEX`.
7. Guarda la conexion.

Si tienes varias conexiones, fija la que usara el agente en `.env`:

```dotenv
FOUNDRY_SEARCH_CONNECTION_NAME=<nombre-de-la-conexion>
# o
FOUNDRY_SEARCH_CONNECTION_ID=<id-completo-de-la-conexion>
```

### Limpiar la demo y volver a cero

Ejecuta desde `phases/04-transit`:

```powershell
python clean/00_show_cleanup_plan.py
python clean/99_clean_all.py --yes
```

La limpieza elimina indice, indexer, skillset, data source, blobs de la demo, versiones del agente Foundry y datos locales. Conserva los recursos base: Azure OpenAI/Foundry deployments, Azure AI Search service, Storage Account y Azure AI Foundry Project.

### Levantar backend

```powershell
cd phases/04-transit
pip install -r demo/backend/requirements.txt
uvicorn demo.backend.main:app --reload --port 8000
```

La API queda disponible en `http://localhost:8000`.

Endpoints principales:

- `GET /api/documents`: lista chunks del indice.
- `POST /api/ask/local`: responde con Agent Framework local y Azure AI Search.
- `POST /api/ask/foundry`: responde con agente nativo de Azure AI Foundry.
- `POST /api/ask/foundry/stream`: transmite la respuesta del agente con Server-Sent Events y devuelve chunks enriquecidos con scores de Azure AI Search.

### Levantar frontend

```powershell
cd phases/04-transit/demo/app
npm install
npm run dev
```

Abre `http://localhost:3000`.

## Tecnicas RAG que se pueden explicar

- **Chunking**: division del documento en fragmentos manejables con solapamiento.
- **Embeddings**: representacion vectorial para similitud semantica.
- **Metadata**: titulo, pagina, fuente, categoria y mision para filtrar y citar.
- **Busqueda hibrida**: combina texto clave (BM25) con similitud vectorial.
- **Semantic Reranker**: reordena los candidatos con un modelo de ranking semantico.
- **Tool calling**: el agente usa la busqueda como herramienta antes de responder.
- **Grounded prompting**: instrucciones para responder solo con evidencia recuperada.

## Buenas practicas y mejoras sugeridas

- Mantener un `.env.example` actualizado y no versionar `.env`.
- Usar nombres de deployments explicitos en la documentacion y la UI.
- Evitar que el frontend tenga `http://localhost:8000` hardcodeado; moverlo a `NEXT_PUBLIC_API_BASE_URL`.
- Agregar una evaluacion ligera con preguntas esperadas, citas esperadas y casos fuera del corpus.
- Registrar query, chunks recuperados, scores, uso de rerank y latencia por endpoint.
- Mostrar claramente cuando la respuesta no tiene evidencia suficiente.
- Separar configuracion de desarrollo y produccion, especialmente CORS e identidad.
- En produccion, usar Managed Identity, filtros por permisos, sanitizacion de documentos y defensa contra prompt injection.

## Recomendaciones para presentar

- Empieza con una pregunta simple y muestra los chunks recuperados antes de mostrar la respuesta.
- Luego usa una pregunta sin palabras exactas del documento para explicar embeddings.
- Despues compara sin rerank vs. con rerank en el playground.
- Para mostrar el impacto del rerank, usa: `Que mision busca senales de vida antigua en el crater Jezero?`. La demo usa grounding estricto: sin rerank se mezclan fragmentos de Phoenix/Curiosity y la respuesta debe reconocer falta de evidencia; con Semantic Reranker suben los fragmentos de Mars 2020 Perseverance.
- Cierra con una pregunta fuera del corpus para demostrar grounding y limites.
