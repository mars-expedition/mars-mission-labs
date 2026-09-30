import argparse
import os
from collections.abc import Iterable

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from _common import add_yes_arg, confirm, load_phase_env, print_header


_TYPE_ERROR = object()


def _try_call(callable_obj, *args, **kwargs):
    try:
        return callable_obj(*args, **kwargs)
    except TypeError:
        return _TYPE_ERROR


def list_agent_versions(agents, agent_name: str) -> list[object]:
    candidates = [
        lambda: _try_call(agents.list_versions, agent_name=agent_name)
        if hasattr(agents, "list_versions")
        else None,
        lambda: _try_call(agents.list_versions, agent_name)
        if hasattr(agents, "list_versions")
        else None,
        lambda: _try_call(agents.get_versions, agent_name=agent_name)
        if hasattr(agents, "get_versions")
        else None,
        lambda: _try_call(agents.get_versions, agent_name)
        if hasattr(agents, "get_versions")
        else None,
    ]

    for candidate in candidates:
        result = candidate()
        if result is None or result is _TYPE_ERROR:
            continue
        if isinstance(result, Iterable) and not isinstance(result, (str, bytes, dict)):
            return list(result)
        return [result]

    return []


def delete_agent_version(agents, *, agent_name: str, agent_version: str) -> None:
    result = _try_call(
        agents.delete_version,
        agent_name=agent_name,
        agent_version=agent_version,
    )
    if result is not _TYPE_ERROR:
        return

    result = _try_call(agents.delete_version, agent_name, agent_version)
    if result is not _TYPE_ERROR:
        return

    raise RuntimeError(
        "No se pudo invocar agents.delete_version con las firmas esperadas."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Elimina versiones del agente nativo de Azure AI Foundry usado en la demo."
    )
    add_yes_arg(parser)
    args = parser.parse_args()

    load_phase_env()

    project_endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT") or os.getenv(
        "AZURE_AI_FOUNDRY_PROJECT_ENDPOINT"
    )
    agent_name = os.getenv("FOUNDRY_AGENT_NAME", "marsrag-native-agent")
    explicit_version = os.getenv("FOUNDRY_AGENT_VERSION")

    print_header("03 - Limpieza de Azure AI Foundry Agent")

    if not project_endpoint:
        print("No hay FOUNDRY_PROJECT_ENDPOINT. Saltando limpieza de Foundry.")
        return

    print("Proyecto:", project_endpoint)
    print("Agente:", agent_name)
    if explicit_version:
        print("Version explicita:", explicit_version)

    if not confirm("\nEsta accion eliminara versiones del agente Foundry.", yes=args.yes):
        print("Cancelado.")
        return

    credential = DefaultAzureCredential()
    project_client = AIProjectClient(endpoint=project_endpoint, credential=credential)

    with project_client:
        agents = project_client.agents

        if explicit_version:
            delete_agent_version(
                agents,
                agent_name=agent_name,
                agent_version=explicit_version,
            )
            print(f"- version {explicit_version}: eliminada")
            return

        versions = list_agent_versions(agents, agent_name)
        if not versions:
            available = [
                name
                for name in dir(agents)
                if "version" in name.lower() or "agent" in name.lower()
            ]
            print("No pude listar versiones automaticamente con este SDK.")
            print("Define FOUNDRY_AGENT_VERSION en .env y vuelve a ejecutar este script.")
            print("Metodos relacionados disponibles:", ", ".join(available))
            return

        deleted = 0
        for version in versions:
            version_name = getattr(version, "version", None) or getattr(
                version,
                "agent_version",
                None,
            )
            name = getattr(version, "name", None) or agent_name
            if not version_name:
                print(f"- no pude identificar version en: {version}")
                continue

            delete_agent_version(
                agents,
                agent_name=name,
                agent_version=str(version_name),
            )
            deleted += 1
            print(f"- {name} / version {version_name}: eliminada")

    print(f"\nVersiones eliminadas: {deleted}")


if __name__ == "__main__":
    main()
