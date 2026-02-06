from src.garimpo.services.extract import extract
from src.garimpo.services.bot import PromoBot
from src.garimpo.infra.repository import CloudProductRepository
import asyncio

if __name__ == "__main__":
    extracts = extract()
    extracts.shopify()
    extracts.nuvemshop()

    gcp = CloudProductRepository()
    gcp.sync_local_to_cloud()
    
    telegram_bot = PromoBot()
    asyncio.run(telegram_bot.send_promotions())
    
