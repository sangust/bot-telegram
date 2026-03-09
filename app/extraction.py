from app.src.services.extract import Extractor
from app.src.services.mlExtract import MLExtractor
import logging

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    e0 = Extractor()
    e1 = MLExtractor()
    e1.extract()