import asyncio
from app.infrastructure.ai_client import AIClient


async def test():
    client = AIClient()
    result = await client.generate_json(
        prompt="Extrae nombre y cantidad de: '100 bultos de cemento gris'",
        system_instruction="Responde solo JSON con las claves 'material' y 'cantidad'.",
    )
    print("Respuesta de la IA:", result)


asyncio.run(test())