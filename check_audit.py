import asyncio
import asyncpg
from app.core.config import settings


async def check():
    url = settings.database_url.replace('+asyncpg', '')
    conn = await asyncpg.connect(url)
    rows = await conn.fetch(
        "SELECT action, resource_type, resource_id, actor_user_id, details, created_at "
        "FROM audit_logs ORDER BY created_at"
    )
    for r in rows:
        print(dict(r))
    await conn.close()


asyncio.run(check())