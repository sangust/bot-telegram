import asyncio
import os
import subprocess
import sys

import uvicorn

from app.src.infrabackend.config import HOST, PORT, SCRAPER_INTERVAL_SECONDS, WORKER_POLL_SECONDS
from app.src.services.delivery import run_worker_loop
from app.src.services.scraper import run_scraper_loop, run_scraper_pass
import logging

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

def main() -> None:
    role = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("APP_ROLE", "web")).strip().lower()
    logger.info("Inicializando runtime com APP_ROLE=%s", role)

    if role == "migrate":
        subprocess.run(["alembic", "upgrade", "head"], check=True)
        return

    if role == "worker":
        logger.info("Worker iniciado com poll de %ss", WORKER_POLL_SECONDS)
        asyncio.run(run_worker_loop(WORKER_POLL_SECONDS))
        return

    if role == "scraper":
        logger.info("Scraper iniciado com intervalo de %ss; o primeiro ciclo roda imediatamente", SCRAPER_INTERVAL_SECONDS)
        asyncio.run(run_scraper_loop(SCRAPER_INTERVAL_SECONDS))
        return

    if role == "scraper_once":
        logger.info("Executando um único ciclo de scraper")
        run_scraper_pass()
        return

    logger.info("Web iniciado em http://%s:%s", HOST, PORT)
    uvicorn.run("app.api.main:app", host=HOST, port=PORT)


if __name__ == "__main__":
    main()
