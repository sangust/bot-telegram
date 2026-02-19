from app.src.services.extract import extract
from app.src.services.bot import PromoBot
from app.src.infrabackend.repository import CloudProductRepository
import asyncio

if __name__ == "__main__":
    extracts = extract()
    extracts.shopify()
    extracts.nuvemshop()

    gcp = CloudProductRepository()
    gcp.normalize_to_cloud()
    gcp.sync_local_to_cloud()
    
    telegram_bot = PromoBot()
    asyncio.run(telegram_bot.send_promotions())
    
