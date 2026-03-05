from app.src.services.extract import Extractor
import logging

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    e = Extractor()
    e.shopify()

    e2 = Extractor()
    e2.nuvemshop()