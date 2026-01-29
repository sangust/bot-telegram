from .config import BOT, CHAT_ID, SESSION
from sqlalchemy import select, or_, and_
from .models import Product
from .extract import executar_coleta
from collections import defaultdict
from typing import Dict, List
import asyncio

def buscar_produtos_desconto():
    session = SESSION()
    try:
        return session.scalars(
        select(Product)
        .where(
                Product.disponivel.is_(True),
                Product.preco_atual < Product.preco_real
            )
        .order_by(Product.preco_atual.asc())
        ).all()
    finally:
        session.close()



def formatar_produto_agrupado(produto: dict):
    tamanhos = ", ".join(produto["tamanhos"])

    texto = (
        f"""{produto['marca']} | {produto['nome']}
Valor Cheio -> R$ {produto['preco_real']:.2f}
Valor Atual -> R$ {produto['preco_atual']:.2f}

Tamanhos disponíveis: {tamanhos}

LINK: {produto['link']}"""
    )

    return texto, produto["imagem"]



def agrupar_produtos(produtos: List[Product]) -> List[dict]:
    agrupados: Dict[tuple, dict] = {}

    for p in produtos:
        chave = (
            p.marca,
            p.nome,
            p.link,
            p.preco_atual,
            p.preco_real,
        )

        if chave not in agrupados:
            agrupados[chave] = {
                "marca": p.marca,
                "nome": p.nome,
                "link": p.link,
                "preco_atual": p.preco_atual,
                "preco_real": p.preco_real,
                "imagem": p.imagem,
                "tamanhos": set(),
            }

        agrupados[chave]["tamanhos"].add(p.tamanho)

    # converte set → lista ordenada
    for produto in agrupados.values():
        produto["tamanhos"] = sorted(produto["tamanhos"])

    return list(agrupados.values())



async def enviar_promos():
    produtos = buscar_produtos_desconto()

    if not produtos:
        return

    produtos_agrupados = agrupar_produtos(produtos)

    for produto in produtos_agrupados:
        texto, imagem = formatar_produto_agrupado(produto)

        try:
            await BOT.send_photo(
                chat_id=CHAT_ID,
                photo=imagem,
                caption=texto
            )
        except Exception as e:
            print(f"[ERRO TELEGRAM] {e}")

        await asyncio.sleep(12)






if __name__ == "__main__":
    executar_coleta()
    asyncio.run(enviar_promos())