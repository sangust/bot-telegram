import httpx
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, tuple_
from datetime import datetime, timezone

from .config import SHOP_URLS, SESSION
from .models import Product
from .schemas import ProductSchema



def safe_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None



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
                    # ---- dados básicos
                    link = url.replace(
                        "/products.json?limit=250",
                        f"/products/{item['handle']}"
                    )

                    images = item.get("images") or []
                    imagem = images[0].get("src") if images else None

                    preco_atual = safe_float(variant.get("price"))
                    compare_at_price = safe_float(variant.get("compare_at_price"))

                    if preco_atual is None:
                        raise ValueError("price inválido")

                    if compare_at_price and compare_at_price > preco_atual:
                        preco_real = compare_at_price
                    else:
                        preco_real = preco_atual

                    produto = ProductSchema(
                        marca=marca,
                        nome=item["title"],
                        variante_id=variant["id"],
                        preco_atual=preco_atual,
                        preco_real=preco_real,
                        disponivel=variant["available"],
                        data_coleta=datetime.now(timezone.utc),
                        tamanho=variant["title"],
                        link=link,
                        imagem=imagem
                    )

                    produtos_validos.append(produto)

                except Exception as e:
                    print(
                        f"[VALIDAÇÃO] Produto ignorado | Marca={marca} | "
                        f"Nome={item.get('title')} | Erro={e}"
                    )

    except Exception as e:
        print(f"[ERRO COLETA] Marca={marca} | Erro={e}")

    return produtos_validos


# =========================
# Persistência
# =========================

def salvar_no_banco(
    produtos: List[ProductSchema],
    session: Session
) -> List[Product]:

    chaves = [(p.marca, p.variante_id) for p in produtos]

    existentes = session.scalars(
        select(Product).where(
            tuple_(Product.marca, Product.variante_id).in_(chaves)
        )
    ).all()

    mapa_existentes = {
        (p.marca, p.variante_id): p
        for p in existentes
    }

    produtos_alterados: List[Product] = []

    for produto in produtos:
        chave = (produto.marca, produto.variante_id)

        # ---- PRODUTO JÁ EXISTE
        if chave in mapa_existentes:
            p = mapa_existentes[chave]

            if (
                p.preco_atual != produto.preco_atual
                or p.preco_real != produto.preco_real
                or p.disponivel != produto.disponivel
            ):
                p.preco_atual = produto.preco_atual
                p.preco_real = produto.preco_real
                p.disponivel = produto.disponivel
                p.data_coleta = produto.data_coleta

                produtos_alterados.append(p)

        # ---- PRODUTO NOVO
        else:
            novo_produto = Product(
                marca=produto.marca,
                nome=produto.nome,
                variante_id=produto.variante_id,
                preco_atual=produto.preco_atual,
                preco_real=produto.preco_real,
                disponivel=produto.disponivel,
                data_coleta=produto.data_coleta,
                tamanho=produto.tamanho,
                link=produto.link,
                imagem=produto.imagem,
            )

            session.add(novo_produto)
            produtos_alterados.append(novo_produto)

    if produtos_alterados:
        session.commit()

    return produtos_alterados


# =========================
# Orquestração
# =========================

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
