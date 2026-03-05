import asyncio
import logging
from telegram import Bot
from telegram.request import HTTPXRequest
from ..infrabackend.repository import BotRepository
from ..infrabackend.database import SessionLocal
from ..domain.models import Product, Bot as meuBot


#Mostrar logs.
logger = logging.getLogger(__name__)


class Afilibot:
    """
    Bot De envio automatico de promocoes de lojas selecionadas pelo usuario, 
    com o link de afiliado imbutido, gerando renda de comissão para o assinante.
    """
    def __init__(self, bot_token: str, chat_id: str | None):
        self.chat_id = chat_id
        self._token  = bot_token
        self.bot     = Bot(
            token   = bot_token,
            request = HTTPXRequest(
                connect_timeout = 30,
                read_timeout    = 30,
                write_timeout   = 30,
                pool_timeout    = 30,
            ),
        )

    @staticmethod
    def _format_price(value) -> str:
        try:
            return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _format_message(product: Product, affiliate_link: str | None) -> str:
        link = product.link
        if affiliate_link:
            separator = "&" if "?" in link else "?"
            link = f"{link}{separator}{affiliate_link}"

        discount_pct = ""
        try:
            full = float(product.full_price)
            disc = float(product.discount_price)
            if full > 0 and disc < full:
                pct = round((1 - disc / full) * 100)
                discount_pct = f"  {pct}% OFF"
        except Exception:
            pass

        return (
            f"<b>🔥 {product.brand} | {product.name}</b>\n\n"
            f"Preço Normal: {Afilibot._format_price(product.full_price)}\n"
            f"Preço Com Desconto: {Afilibot._format_price(product.discount_price)} - {discount_pct}\n\n"
            f"📐 Tamanhos: {product.size or 'Único'}\n\n"
            f"<a href=\"{link}\">🔗 Comprar agora</a>"
        )
    

    async def send_promotions(self, brands: list[str], affiliate_link: str | None = None) -> dict:
    # Buscar produtos e fechar sessão imediatamente
        with SessionLocal() as db:
            botrepo = BotRepository(db)
            products:list[str] = botrepo.discount_products(brands=brands)

        if not products:
            logger.info("Nenhum produto com desconto para brands=%s", brands)
            return {"sent": 0}

        sent = 0
        batch_counter = 0

        for product in products:
            await asyncio.sleep(10)

            try:
                msg = self._format_message(product, affiliate_link)

                await self.bot.send_photo(
                    chat_id=self.chat_id,
                    photo=product.image,
                    caption=msg,
                    parse_mode="HTML",
                )

                sent += 1
                batch_counter += 1

                # Atualiza métricas a cada 5 envios
                if batch_counter == 5:
                    with SessionLocal() as db:
                        db.query(meuBot).filter(
                            meuBot.bot_token == self._token
                        ).update(
                            {
                                meuBot.today_sent: meuBot.today_sent + batch_counter,
                                meuBot.all_sent: meuBot.all_sent + batch_counter,
                            },
                            synchronize_session=False,
                        )
                        db.commit()
                    batch_counter = 0

            except Exception as e:
                logger.error("Erro ao enviar produto %s: %s", product.name, e)

        # Atualiza o restante que não fechou múltiplo de 5
        if batch_counter > 0:
            with SessionLocal() as db:
                db.query(meuBot).filter(
                    meuBot.bot_token == self._token
                ).update(
                    {
                        meuBot.today_sent: meuBot.today_sent + batch_counter,
                        meuBot.all_sent: meuBot.all_sent + batch_counter,
                    },
                    synchronize_session=False,
                )
                db.commit()

        logger.info("Envio concluído: %d produtos enviados", sent)
        return {"sent": sent}