import os

from _common import PHASE_DIR, load_phase_env, print_header


def main():
    load_phase_env()

    search_index = os.getenv("AZURE_SEARCH_INDEX", "<sin AZURE_SEARCH_INDEX>")
    storage_container = os.getenv("AZURE_STORAGE_CONTAINER", "<sin AZURE_STORAGE_CONTAINER>")
    blob_prefix = os.getenv("AZURE_STORAGE_BLOB_PREFIX", "mars-rag").strip("/")
    foundry_agent = os.getenv("FOUNDRY_AGENT_NAME", "marsrag-native-agent")

    print_header("Plan de limpieza de la demo RAG")
    print("Base de configuracion:", PHASE_DIR / ".env")
    print()
    print("Se limpiaran recursos derivados de la demo:")
    print(f"1. Azure AI Search indexer:   {search_index}-blob-indexer")
    print(f"2. Azure AI Search skillset:  {search_index}-textsplit-skillset")
    print(f"3. Azure AI Search datasource:{search_index}-blob-datasource")
    print(f"4. Azure AI Search index:     {search_index}")
    print(f"5. Azure Blob container:      {storage_container}")
    print(f"6. Azure Blob prefix:         {blob_prefix or '(raiz del contenedor)'}")
    print(f"7. Azure AI Foundry agent:    {foundry_agent}")
    print(f"8. Datos locales:             {PHASE_DIR / 'data'}")
    print()
    print("No se eliminan recursos base:")
    print("- Resource Group")
    print("- Azure OpenAI / Foundry model deployments")
    print("- Azure AI Search service")
    print("- Storage Account")
    print("- Azure AI Foundry Project ni sus conexiones")
    print()
    print("Orden recomendado:")
    print("python clean/01_clean_search_assets.py --yes")
    print("python clean/02_clean_storage_blobs.py --yes")
    print("python clean/03_clean_foundry_agent.py --yes")
    print("python clean/04_clean_local_data.py --yes")
    print()
    print("O todo junto:")
    print("python clean/99_clean_all.py --yes")


if __name__ == "__main__":
    main()
