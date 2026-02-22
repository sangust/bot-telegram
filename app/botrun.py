from app.src.services.extract import extract
from app.src.services.bot import PromoBot


async def afilibot(chat_id, stores, link_afiliado=None):
    extracts = extract()
    extracts.shopify()
    extracts.nuvemshop()

    telegram_bot = PromoBot(CHAT_ID=chat_id)
    await telegram_bot.send_promotions(stores)
