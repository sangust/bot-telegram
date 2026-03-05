from app.src.services.bot import Afilibot


async def afilibot(chat_id: str, brands: list[str], bot_token: str, affiliate_link: str | None = None):
    telegram_bot = Afilibot(bot_token=bot_token, chat_id=chat_id)
    await telegram_bot.send_promotions(brands=brands, affiliate_link=affiliate_link)