import argparse
import os

from _common import (
    add_yes_arg,
    confirm,
    create_search_admin_client,
    delete_search_resource,
    load_phase_env,
    print_header,
    require_env,
)


def main():
    parser = argparse.ArgumentParser(
        description="Elimina recursos derivados de Azure AI Search para la demo RAG."
    )
    add_yes_arg(parser)
    args = parser.parse_args()

    load_phase_env()
    env = require_env("AZURE_SEARCH_ENDPOINT", "AZURE_SEARCH_INDEX")

    index_name = env["AZURE_SEARCH_INDEX"]
    indexer_name = os.getenv("AZURE_SEARCH_INDEXER_NAME", f"{index_name}-blob-indexer")
    skillset_name = os.getenv("AZURE_SEARCH_SKILLSET_NAME", f"{index_name}-textsplit-skillset")
    datasource_name = os.getenv("AZURE_SEARCH_DATASOURCE_NAME", f"{index_name}-blob-datasource")

    resources = [
        ("indexers", indexer_name),
        ("skillsets", skillset_name),
        ("datasources", datasource_name),
        ("indexes", index_name),
    ]

    print_header("01 - Limpieza de Azure AI Search")
    print("Endpoint:", env["AZURE_SEARCH_ENDPOINT"])
    for collection, name in resources:
        print(f"- {collection}: {name}")

    if not confirm("\nEsta accion eliminara recursos de Azure AI Search.", yes=args.yes):
        print("Cancelado.")
        return

    client, endpoint, api_version = create_search_admin_client()
    with client:
        for collection, name in resources:
            delete_search_resource(
                client,
                endpoint=endpoint,
                api_version=api_version,
                collection=collection,
                name=name,
            )

    print("\nAzure AI Search quedo limpio para recrear el indice desde cero.")


if __name__ == "__main__":
    main()
