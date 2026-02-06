from src.garimpo.services.extract import extract
from src.garimpo.services.bot import PromoBot
from src.garimpo.infra.repository import CloudProductRepository
import asyncio

if __name__ == "__main__":
    
    bot = PromoBot()
    asyncio.run(bot.send_promotions("yungceo"))
    
