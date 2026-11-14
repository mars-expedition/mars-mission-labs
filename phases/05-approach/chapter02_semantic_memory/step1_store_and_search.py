import asyncio

from mission_control import create_memory

USER_ID = "comandante-ana-torres"  # separa la memoria de cada persona


async def main() -> None:
    memory = create_memory()

    await memory.add(
        [
            {"role": "user", "content": "Soy la comandante Ana Torres y mi nave se llama Quilla-7."},
            {"role": "user", "content": "Prefiero los reportes en una sola línea, sin rodeos."},
        ],
        user_id=USER_ID,
    )  # Mem0 extrae los hechos relevantes de estos mensajes y los guarda como vectores

    results = await memory.search(
        "¿Cómo le gusta recibir los reportes a la comandante?",
        filters={"user_id": USER_ID},
    )
    for item in results["results"]:
        print(f"[{item['score']:.2f}] {item['memory']}")


if __name__ == "__main__":
    asyncio.run(main())
