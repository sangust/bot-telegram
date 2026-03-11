import asyncio
import logging

from app.src.infrabackend.config import ML_CATEGORIES, PROXY_URLS
from app.src.services.extract import Extractor
from app.src.services.mlExtract import MLExtractor

logger = logging.getLogger(__name__)


def _run_source(name: str, operation) -> None:
    try:
        operation()
    except Exception:
        logger.exception("Erro no scraper %s", name)


def run_scraper_pass() -> None:
    logger.info("Iniciando ciclo de scrapers")
    #_run_source("shopify", lambda: Extractor().shopify())
    #_run_source("nuvemshop", lambda: Extractor().nuvemshop())
    logger.info(
        "Executando scraper do Mercado Livre com %d categorias e %d proxies configurados",
        len(ML_CATEGORIES),
        len(PROXY_URLS),
    )
    _run_source("mercadolivre", lambda: MLExtractor(categories=ML_CATEGORIES).extract())
    logger.info("Ciclo de scrapers concluído")


async def run_scraper_loop(interval_seconds: float) -> None:
    while True:
        try:
            await asyncio.to_thread(run_scraper_pass)
        except Exception:
            logger.exception("Erro no scraper")
        logger.info("Próximo ciclo de scraper em %ss", interval_seconds)
        await asyncio.sleep(interval_seconds)
