# check_encoding.py
import asyncio
import asyncpg
from app.core.config import settings


async def check():
    url = settings.database_url.replace('+asyncpg', '')
    conn = await asyncpg.connect(url)
    row = await conn.fetchrow("SELECT material_name, specs FROM provider_inventory WHERE id = 2")
    print(dict(row))
    await conn.close()


asyncio.run(check())