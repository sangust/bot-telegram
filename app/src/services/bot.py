from telegram import Bot
from telegram.request import HTTPXRequest
from ..infrabackend.repository import LocalProductRepository
import asyncio
import os

class PromoBot():
    def __init__(self, BOT_TOKEN = os.getenv("BOT_TOKEN"), CHAT_ID = os.getenv("CHAT_ID")):
        self.chat_id = CHAT_ID
        self.REQUEST = HTTPXRequest(
            connect_timeout=30,
            read_timeout=30,
            write_timeout=30,
            pool_timeout=30
        )
        self.bot = Bot(token=BOT_TOKEN, request=self.REQUEST)

    
    async def send_promotions(self, stores):
        discount_products = LocalProductRepository().discount_products(stores=stores)
        if not discount_products:
            return
    
        for product in discount_products:
            msg = f"""
🔥 {product.marca} || {product.nome}\n
💰 Preço Normal: R$ {product.preco_real}
💰 Preço Atual: R$ {product.preco_atual}

Tamanhos Disponivel: {product.tamanhos_disponiveis}
🔗Link:\n {product.link}
                """
            await self.bot.send_photo(
                chat_id=self.chat_id,
                photo=product.imagem,
                caption=msg)
            await asyncio.sleep(10)