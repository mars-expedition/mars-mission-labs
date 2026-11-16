import asyncio
import os

from azure.ai.evaluation import AzureOpenAIModelConfiguration, CoherenceEvaluator, RelevanceEvaluator

from mission_control import create_mission_control

MODEL_CONFIG: AzureOpenAIModelConfiguration = {
    "azure_deployment": os.getenv("AZURE_OPENAI_CHAT_COMPLETION_MODEL"),
    "azure_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
    "api_key": os.getenv("AZURE_OPENAI_API_KEY"),
}


async def main() -> None:
    query = "¿Cómo está el guiado durante la entrada? Consulta el piloto automático."

    mission_control = create_mission_control()
    response = await mission_control.run(query)
    print(f"CONTROL: {response.text}")

    relevance = RelevanceEvaluator(model_config=MODEL_CONFIG)
    coherence = CoherenceEvaluator(model_config=MODEL_CONFIG)

    print("Relevancia:", relevance(query=query, response=response.text))
    print("Coherencia:", coherence(query=query, response=response.text))


if __name__ == "__main__":
    asyncio.run(main())
