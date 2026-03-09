import asyncio
import os
import subprocess

import uvicorn

from app.src.infrabackend.config import HOST, PORT, SCRAPER_INTERVAL_SECONDS, WORKER_POLL_SECONDS
from app.src.services.delivery import run_worker_loop
from app.src.services.scraper import run_scraper_loop


def main() -> None:
    role = os.getenv("APP_ROLE", "web").strip().lower()

    if role == "migrate":
        subprocess.run(["alembic", "upgrade", "head"], check=True)
        return

    if role == "worker":
        asyncio.run(run_worker_loop(WORKER_POLL_SECONDS))
        return

    if role == "scraper":
        asyncio.run(run_scraper_loop(SCRAPER_INTERVAL_SECONDS))
        return

    uvicorn.run("app.api.main:app", host=HOST, port=PORT)


if __name__ == "__main__":
    main()
