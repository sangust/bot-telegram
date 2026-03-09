import logging

from app.src.services.scraper import run_scraper_pass

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    run_scraper_pass()