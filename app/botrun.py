from app.src.services.bot import PromoBot
from app.src.infrabackend.database import LocalDatabase
from app.src.infrabackend.repository import LocalRepository
from app.src.domain.models import Bot
from datetime import date


async def afilibot(chat_id, stores, bot_token, link_afiliado=None):
    telegram_bot = PromoBot(CHAT_ID=chat_id, BOT_TOKEN=bot_token)
    await telegram_bot.send_promotions(stores)

    db = LocalDatabase()
    session = db.SESSION()
    try:
        repo = LocalRepository(db)
        products = repo.discount_products(stores=stores)
        count = len(products) if products else 0

        bot_db = session.query(Bot).filter(Bot.bot_token == bot_token).first()
        if bot_db and count > 0:
            bot_db.today_sent = count
            bot_db.all_sent = (bot_db.all_sent or 0) + count
            session.commit()
            print(f"[botrun] Contadores atualizados: hoje={bot_db.today_sent}, total={bot_db.all_sent}")
    except Exception as e:
        session.rollback()
        print(f"[botrun] Erro ao atualizar contadores: {e}")
    finally:
        session.close()