import httpx
from datetime import datetime, timezone
from ..infrabackend.config import SHOPIFY_URLS, NUVEMSHOP_URLS
from ..infrabackend.schemas import ProductSchema
from ..infrabackend.database import LocalDataBase
from ..infrabackend.repository import LocalProductRepository
from bs4 import BeautifulSoup
import re


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

        
    def nuvemshop(self, NUVEMSHOP_URLS = NUVEMSHOP_URLS):
        """
        Extrai produtos de lojas Nuvemshop via web scraping
        
        NUVEMSHOP_URLS deve ser um dict: {"marca": "https://loja.com.br"}
        """
        
        for marca, base_url in NUVEMSHOP_URLS.items():
            try:
                base_url = base_url.rstrip('/')
                produtos_url = f"{base_url}/produtos/"
                
                print(f"[INFO] Iniciando coleta para {marca}")
                
                with httpx.Client(timeout=10, follow_redirects=True) as client:
                    page = 1
                    has_more = True
                    produtos_processados = 0
                    
                    while has_more:
                        try:
                            url = f"{produtos_url}?page={page}"                            
                            response = client.get(url)
                            response.raise_for_status()
                            soup = BeautifulSoup(response.text, 'html.parser')
                            
                            product_items = soup.select('.item-product, .product-item, [itemtype*="Product"]')                            

                            if not product_items:
                                all_links = soup.select('a[href*="/produtos/"]')
                                product_links = []
                                seen_slugs = set()
                                
                                for link in all_links:
                                    href = link.get('href', '')
                                    match = re.search(r'/produtos/([a-z0-9\-]+)/?$', href)
                                    if match:
                                        slug = match.group(1)
                                        if slug not in seen_slugs and slug != '':
                                            seen_slugs.add(slug)
                                            product_links.append((slug, href))
                                                                
                                if not product_links:
                                    print(f"[INFO] Nenhum produto encontrado na página {page}")
                                    has_more = False
                                    break

                            else:
                                product_links = []
                                for item in product_items:
                                    link = item.select_one('a[href*="/produtos/"]')
                                    if link:
                                        href = link.get('href', '')
                                        match = re.search(r'/produtos/([a-z0-9\-]+)/?$', href)
                                        if match:
                                            product_links.append((match.group(1), href))
                            
                            for slug, href in product_links:
                                try:
                                    if href.startswith('http'):
                                        product_url = href
                                    else:
                                        product_url = f"{base_url}{href}"
                                    
                                    print(f"[INFO] Processando produto: {slug}")
                                    
                                    prod_response = client.get(product_url)
                                    prod_response.raise_for_status()
                                    prod_soup = BeautifulSoup(prod_response.text, 'html.parser')
                                    
                                    nome_element = prod_soup.select_one('h1.product-name, h1[itemprop="name"], .product-title h1, h1')
                                    nome = nome_element.get_text(strip=True) if nome_element else slug.replace('-', ' ').title()
                                    
                                    preco_atual = None
                                    
                                    price_selectors = [
                                        'span.price-amount',
                                        'span[itemprop="price"]',
                                        '.product-price span',
                                        '#price_display',
                                        '.js-price-display',
                                    ]
                                    
                                    for selector in price_selectors:
                                        preco_element = prod_soup.select_one(selector)
                                        if preco_element:
                                            preco_text = preco_element.get_text(strip=True)
                                            
                                            preco_clean = re.sub(r'[^\d,]', '', preco_text)
                                            if preco_clean:
                                                try:
                                                    preco_atual = float(preco_clean.replace(',', '.'))
                                                    break
                                                except ValueError:
                                                    continue
                                    
                                    if preco_atual is None:
                                        print(f"[WARN] Preço não encontrado para {slug}, pulando...")
                                        continue
                                    
                                    # Preço comparativo (desconto)
                                    preco_real = preco_atual
                                    compare_element = prod_soup.select_one('.price-compare, .compare-at-price, del, s')
                                    if compare_element:
                                        compare_text = compare_element.get_text(strip=True)
                                        compare_clean = re.sub(r'[^\d,]', '', compare_text)
                                        if compare_clean:
                                            try:
                                                compare_at_price = float(compare_clean.replace(',', '.'))
                                                if compare_at_price > preco_atual:
                                                    preco_real = compare_at_price
                                            except ValueError:
                                                pass
                                    
                                    # Extrai imagem
                                    imagem = None
                                    img_element = prod_soup.select_one('.product-image img, img[itemprop="image"], .js-product-slide-img')
                                    if img_element:
                                        imagem = img_element.get('data-src') or img_element.get('src')
                                        if imagem and imagem.startswith('//'):
                                            imagem = 'https:' + imagem
                                        print(f"[DEBUG] Imagem: {imagem[:50] if imagem else 'Não encontrada'}...")
                                    
                                    # Extrai variantes (tamanhos/cores)
                                    variantes = []
                                    
                                    # Busca por select de variantes
                                    variant_select = prod_soup.select_one('select.js-variation-option, select[name*="variation"]')
                                    if variant_select:
                                        options = variant_select.find_all('option')
                                        print(f"[DEBUG] Variantes encontradas via select: {len(options)}")
                                        for option in options:
                                            variant_text = option.get_text(strip=True)
                                            variant_id = option.get('value', '')
                                            # Pula opções vazias ou de placeholder
                                            if variant_text and variant_text.lower() not in ['selecione', 'escolha', '']:
                                                disponivel = not option.get('disabled', False)
                                                variantes.append({
                                                    'id': variant_id or f"{slug}-{len(variantes)}",
                                                    'tamanho': variant_text,
                                                    'disponivel': disponivel
                                                })
                                    
                                    # Busca por botões de variantes
                                    if not variantes:
                                        variant_buttons = prod_soup.select('.js-variant-option, button[data-option]')
                                        print(f"[DEBUG] Variantes encontradas via botões: {len(variant_buttons)}")
                                        for button in variant_buttons:
                                            variant_text = button.get_text(strip=True)
                                            variant_id = button.get('data-option', '') or button.get('data-value', '')
                                            disponivel = 'disabled' not in button.get('class', [])
                                            if variant_text:
                                                variantes.append({
                                                    'id': variant_id or f"{slug}-{len(variantes)}",
                                                    'tamanho': variant_text,
                                                    'disponivel': disponivel
                                                })
                                    
                                    # Se não encontrou variantes, cria uma padrão
                                    if not variantes:
                                        print(f"[DEBUG] Nenhuma variante encontrada, criando padrão")
                                        # Verifica disponibilidade geral do produto
                                        disponivel = True
                                        out_of_stock = prod_soup.select_one('.out-of-stock, .product-unavailable')
                                        if out_of_stock:
                                            disponivel = False
                                        
                                        variantes.append({
                                            'id': slug,
                                            'tamanho': 'Único',
                                            'disponivel': disponivel
                                        })
                                    
                                    print(f"[DEBUG] Total de variantes a salvar: {len(variantes)}")
                                    
                                    for variant in variantes:
                                        try:
                                            
                                            variant_hash = hash(f"{marca}-{slug}-{variant['tamanho']}") % (10 ** 10)                                            
                                            produto = ProductSchema(
                                                marca=marca,
                                                nome=nome,
                                                variante_id=variant_hash,
                                                preco_atual=preco_atual,
                                                preco_real=preco_real,
                                                disponivel=variant['disponivel'],
                                                data_coleta=datetime.now(timezone.utc).date(),
                                                tamanho=variant['tamanho'],
                                                link=product_url,
                                                imagem=imagem
                                            )
                                            
                                            
                                            try:
                                                self.db.update(product=produto)
                                            except Exception as update_error:
                                                print(f"[DEBUG] Update falhou ({update_error}), tentando add...")
                                                self.db.add(product=produto)
                                            
                                            produtos_processados += 1
                                        
                                        except Exception as e:
                                            print(f"[ERRO VARIANTE] Marca={marca} | Produto={nome} | Variante={variant['tamanho']} | Erro={e}")
                                
                                except Exception as e:
                                    print(f"[ERRO PRODUTO] Marca={marca} | Slug={slug} | Erro={e}")
                                    import traceback
                                    traceback.print_exc()
                            
                            page += 1
                            next_link = soup.select_one('a.next, a[rel="next"], .pagination-next')
                            if not next_link or page > 20:  
                                has_more = False
                        
                        except httpx.HTTPStatusError as e:
                            if e.response.status_code == 404:
                                print(f"[INFO] Página {page} não encontrada (404), finalizando paginação")
                                has_more = False
                            else:
                                raise
                    
                    print(f"[INFO] Total de produtos processados para {marca}: {produtos_processados}")
            
            except Exception as e:
                print(f"[ERRO COLETA] Marca={marca} | Erro={e}")
                import traceback
                traceback.print_exc()
        
        self.db.commit()
        print(f"[SUCCESS] Commit realizado no banco de dados")