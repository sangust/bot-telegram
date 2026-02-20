from app.src.services.extract import extract
from app.src.services.bot import PromoBot
from app.src.infrabackend.repository import CloudProductRepository
import asyncio

async def afilibot(chat_id, stores, link_afiliado=None):
    extracts = extract()
    extracts.shopify(stores)
    
    telegram_bot = PromoBot(CHAT_ID=chat_id)
    await telegram_bot.send_promotions(stores)
