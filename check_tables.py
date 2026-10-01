import asyncio
import asyncpg
from app.core.config import settings


async def test():
    url = settings.database_url.replace('+asyncpg', '')
    conn = await asyncpg.connect(url)
    rows = await conn.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
    )
    print('Tablas creadas:', [r['table_name'] for r in rows])
    await conn.close()


asyncio.run(test())