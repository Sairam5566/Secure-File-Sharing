import asyncio
import logging
from app.main import app, lifespan

logging.basicConfig(level=logging.INFO)

async def test_lifespan():
    print("--- Starting Lifespan ---")
    async with lifespan(app):
        print("--- App is Running ---")
    print("--- Lifespan Ended ---")

if __name__ == "__main__":
    asyncio.run(test_lifespan())
