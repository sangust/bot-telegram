from src.garimpo.services.extract import extract
from src.garimpo.services.bot import PromoBot
from src.garimpo.infra.repository import CloudProductRepository
import asyncio

if __name__ == "__main__":
    extract_1 = extract()
    extract_1.shopify()

    gcp = CloudProductRepository()
    gcp.sync_local_to_cloud()
    
    telegram_bot = PromoBot()
    asyncio.run(telegram_bot.send_promotions())
    
