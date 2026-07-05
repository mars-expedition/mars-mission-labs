# Frontend de la demo RAG

Aplicacion Next.js para presentar visualmente los beneficios de RAG sobre documentos de misiones a Marte.

## Que muestra

- `GET /documents`: exploracion de chunks almacenados en Azure AI Search.
- `GET /chat`: conversacion con streaming del agente nativo de Azure AI Foundry y chunks con scores de Azure AI Search.
- `GET /playground`: comparacion entre busqueda sin rerank y busqueda hibrida con Semantic Reranker.

El frontend consume el backend FastAPI en `http://localhost:8000`.

## Requisitos

- Node.js 18 o superior.
- Backend de la demo ejecutandose en `http://localhost:8000`.
- Indice de Azure AI Search creado y poblado desde el tutorial o notebook de la fase.

## Ejecucion local

Desde `phases/04-transit/demo/app`:

```powershell
npm install
npm run dev
```

Abre `http://localhost:3000`.

## Scripts disponibles

```powershell
npm run dev
npm run build
npm run start
npm run lint
```

## Notas de mejora

- Mover la URL del backend a `NEXT_PUBLIC_API_BASE_URL` para evitar valores hardcodeados.
- Agregar estados de error por endpoint para diferenciar fallas de Search, Foundry y red local.
- Agregar metricas de recuperacion adicionales como latencia y cantidad de chunks.
- Agregar preguntas sugeridas para guiar la presentacion de RAG, rerank y grounding.
