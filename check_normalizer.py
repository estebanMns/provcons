# check_normalizer.py
import asyncio
from app.infrastructure.ai_client import AIClient
from app.modules.documents_ai.normalizer import DocumentNormalizer


async def test():
    client = AIClient()
    normalizer = DocumentNormalizer(client)

    texto_ejemplo = """
    LISTA DE PRECIOS - ACEROS DEL VALLE
    Cemento gris x bulto 50kg - $25,000 - disponible 150 unidades
    Varilla 3/8" x 6m - $18,500 c/u - disponible 300 unidades
    Arena de río - $45,000 por m3 - disponible 20 m3
    """

    items = await normalizer.normalize_inventory_text(texto_ejemplo)
    for item in items:
        print(item)


asyncio.run(test())