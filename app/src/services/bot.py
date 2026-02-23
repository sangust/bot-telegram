from telegram import Bot
from telegram.request import HTTPXRequest
from ..infrabackend.repository import LocalRepository
import asyncio
import os
from ..domain.models import Product

class PromoBot():
    def __init__(self, BOT_TOKEN, CHAT_ID):
        self.chat_id = CHAT_ID
        self.REQUEST = HTTPXRequest(
            connect_timeout=30,
            read_timeout=30,
            write_timeout=30,
            pool_timeout=30
        )
        self.bot = Bot(token=BOT_TOKEN, request=self.REQUEST)

    
    async def send_promotions(self, stores):
        discount_products = LocalRepository().discount_products(stores=stores)
        if not discount_products:
            return {"error, nenhum produto com desconto", 400}
    
        for product in discount_products:
            product: Product
            msg = f"""
🔥 {product.brand} | {product.name}\n
💰 Preço Cheio: R$ {product.full_price}
💰 Preço Com Desconto: R$ {product.discount_price}

Tamanhos Disponíveis: {product.size}
🔗Link:\n {product.link}
                """
            await self.bot.send_photo(
                chat_id=self.chat_id,
                photo=product.image,
                caption=msg)
            await asyncio.sleep(10)