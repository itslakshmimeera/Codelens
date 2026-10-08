import asyncio
import asyncpg

async def main():
    try:
        conn = await asyncpg.connect(
            user="codelens",
            password="codelens_password",
            host="127.0.0.1",
            port=5432,
            database="codelens_db",
        )
        print("DIRECT WINDOWS -> POSTGRES CONNECTION SUCCESSFUL")
        print(await conn.fetchval("SELECT current_user"))
        await conn.close()
    except Exception as e:
        print(type(e).__name__)
        print(e)

asyncio.run(main())
