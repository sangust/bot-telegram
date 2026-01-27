import httpx
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import select, tuple_
from datetime import datetime, timezone
from .config import SHOP_URLS, SESSION
from .models import Product
from .schemas import ProductSchema


def extract_products(marca: str, url: str) -> List[ProductSchema]:
    """
    Coleta produtos de lojas Shopify via products.json
    """
    produtos_validos: List[ProductSchema] = []

    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()

        for item in data.get("products", []):
            for variant in item.get("variants", []):
                try:
                    link = url.replace("/products.json?limit=250", f"/products/{item['handle']}")
                    images = item.get("images") or []
                    imagem = images[0].get("src") if images else None
                    produto = ProductSchema(
                        marca=marca,
                        nome=item["title"],
                        variante_id=variant["id"],
                        preco=float(variant["price"]),
                        disponivel=variant["available"],
                        data_coleta=datetime.now(timezone.utc),
                        tamanho=variant["title"],
                        link=link,
                        imagem=imagem
                        )
                    produtos_validos.append(produto)

                except Exception as e:
                    # Erro de validação ou dado sujo
                    print(
                        f"[VALIDAÇÃO] Produto ignorado | Marca={marca} | "
                        f"Nome={item.get('title')} | Erro={e}"
                    )

    except Exception as e:
        print(f"[ERRO COLETA] Marca={marca} | Erro={e}")

    return produtos_validos


def salvar_no_banco(produtos: List[ProductSchema], session: Session) -> None:
    chaves = [(p.marca, p.variante_id) for p in produtos]

    existentes = session.scalars(
        select(Product).where(
            tuple_(Product.marca, Product.variante_id).in_(chaves)
        )
    ).all()

    # mapa por chave composta
    mapa_existentes = {
        (p.marca, p.variante_id): p
        for p in existentes
    }

    for produto in produtos:
        chave = (produto.marca, produto.variante_id)

    if chave in mapa_existentes:
        p = mapa_existentes[chave]

        if float(p.preco) != float(produto.preco):
            p.preco = produto.preco
            p.disponivel = produto.disponivel
            p.data_coleta = produto.data_coleta

    else:
        session.add(Product(
            marca=produto.marca,
            nome=produto.nome,
            variante_id=produto.variante_id,
            preco=produto.preco,
            disponivel=produto.disponivel,
            data_coleta=produto.data_coleta,
            tamanho=produto.tamanho,
            link=produto.link,
            imagem=produto.imagem
        ))

    session.commit()




def executar_coleta() -> None:
    """
    Orquestra a coleta completa
    """
    session = SESSION()

    try:
        for marca, url in SHOP_URLS.items():
            print(f"[INFO] Coletando {marca}")
            produtos = extract_products(marca, url)

            if produtos:
                salvar_no_banco(produtos, session)
                print(f"[OK] {len(produtos)} registros salvos ({marca})")
            else:
                print(f"[WARN] Nenhum produto válido ({marca})")

    finally:
        session.close()
