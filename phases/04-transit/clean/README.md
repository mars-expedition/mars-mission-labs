# Limpieza de recursos de la demo RAG

Estos scripts dejan la fase lista para ejecutar el tutorial como si fuera desde cero.

Ejecutalos desde `phases/04-transit` con el mismo `.env` usado por el tutorial.

## Que se elimina

- Azure AI Search indexer, skillset, data source e indice.
- Blobs subidos por la demo al contenedor configurado.
- Versiones del agente nativo de Azure AI Foundry, si el SDK permite listarlas.
- Carpeta local `data/`.

## Que no se elimina

- Resource Group.
- Azure OpenAI / Foundry model deployments.
- Azure AI Search service.
- Storage Account.
- Azure AI Foundry Project ni sus conexiones.

Esos son los recursos base que debes tener levantados antes de volver a ejecutar el tutorial.

## Orden recomendado

```powershell
python clean/00_show_cleanup_plan.py
python clean/01_clean_search_assets.py --yes
python clean/02_clean_storage_blobs.py --yes
python clean/03_clean_foundry_agent.py --yes
python clean/04_clean_local_data.py --yes
```

Tambien puedes correr todo junto:

```powershell
python clean/99_clean_all.py --yes
```

Si prefieres eliminar el contenedor completo en vez de solo el prefijo `AZURE_STORAGE_BLOB_PREFIX`:

```powershell
python clean/99_clean_all.py --yes --delete-container
```

## Volver a correr el tutorial

Despues de limpiar:

```powershell
python tutorial/01_download_data.py
python tutorial/02_prepare_and_embed.py
python tutorial/03_setup_search_index.py
python tutorial/04_agent_with_rag.py
python tutorial/05_agent_comparison.py
python tutorial/06_native_foundry_agent.py
```
