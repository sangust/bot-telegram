import httpx
from datetime import datetime, timezone
from ..infra.config import SHOPIFY_URLS
from ..infra.schemas import ProductSchema
from ..infra.database import LocalDataBase
from ..infra.repository import LocalProductRepository


class extract:
    def __init__(self, db = LocalDataBase, query=LocalProductRepository):
        self.db = query(db=db())
    
    def shopify(self, SHOPIFY_URLS = SHOPIFY_URLS):
        for marca, url in SHOPIFY_URLS.items():
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
                                preco_atual = float(variant.get("price"))
                                raw_compare = variant.get("compare_at_price")
                                compare_at_price = float(raw_compare) if raw_compare else None

                                if preco_atual is None:
                                    raise ValueError("price inválido")

                                if compare_at_price and compare_at_price > preco_atual:
                                    preco_real = compare_at_price
                                else:
                                    preco_real = preco_atual

                                produto = ProductSchema(
                                    marca=marca,
                                    nome=item["title"],
                                    variante_id=int(variant["id"]),
                                    preco_atual=preco_atual,
                                    preco_real=preco_real,
                                    disponivel=variant["available"],
                                    data_coleta=datetime.now(timezone.utc).date(),
                                    tamanho=variant["title"],
                                    link=link,
                                    imagem=imagem
                                )
                                try:
                                    self.db.update(product=produto)
                                except:
                                    self.db.add(product=produto)

                            except Exception as e:
                                print(
                                    f"[VALIDAÇÃO] Produto ignorado | Marca={marca} | "
                                    f"Nome={item.get('title')} | Erro={e}"
                                )

            except Exception as e:
                print(f"[ERRO COLETA] Marca={marca} | Erro={e}")
        
        self.db.commit() 