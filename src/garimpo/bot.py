from .config import BOT, CHAT_ID, SESSION
from sqlalchemy import select
from .models import Product
import asyncio

def buscar_todos_produtos(nome: str = 'ËVIL FRIEND'):
    session = SESSION()
    try:
        produtos = session.scalars(
            select(Product)
            .where(Product.nome == nome)
            .order_by(Product.data_coleta.desc())
            .limit(1)
        ).all()

        return produtos
    finally:
        session.close()

def formatar_produtos(produtos):
    linhas = []

    for p in produtos:
        linhas.append(
            f"""Marca: {p.marca} | {p.nome} 
TAM: {p.tamanho} | R$ {p.preco:.2f}
LINK: {p.link}"""
        )

    return "\n".join(linhas), p.imagem

async def enviar_promos():

    text, imagem = formatar_produtos(buscar_todos_produtos())
    await BOT.send_photo(chat_id=CHAT_ID, photo=imagem, caption=text)


if __name__ == "__main__":
    asyncio.run(enviar_promos())