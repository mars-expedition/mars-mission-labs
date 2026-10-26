# MISIÓN MARTE · Labs

Código de los retos del bootcamp **MISIÓN MARTE** (Microsoft Agent Framework).
La guía completa de cada fase está en la web: **https://mars-expedition.github.io/mars-mission/**

## Cómo ejecutar

Requisitos: [uv](https://docs.astral.sh/uv/) (gestiona Python y las dependencias por ti).

Crea un archivo `.env` en la raíz del proyecto (usa `.env.example` como plantilla) con tu
API key de OpenAI o tu token gratis de GitHub Models. Luego:

```bash
uv run phases/01-ignition/01_hello_agent.py
```

Las fases 03 y 04 usan Azure y tienen su propio `.env.example` dentro de su carpeta.
Sigue la guía de cada fase en la web.

## Fases

| Fase | Reto | Estado |
|------|------|--------|
| 01 · IGNITION | [phases/01-ignition](phases/01-ignition) | ✅ Disponible |
| 03 · ORBIT | [phases/03-orbit](phases/03-orbit) | ✅ Disponible |
| 04 · TRANSIT | [phases/04-transit](phases/04-transit) | ✅ Disponible |
| 02, 05–08 | — | 🔒 Próximamente |
