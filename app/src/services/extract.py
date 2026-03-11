import hashlib
import logging
import re

import httpx
from bs4 import BeautifulSoup

from ..infrabackend.config import SHOPIFY_URLS, NUVEMSHOP_URLS
from ..infrabackend.schemas import ProductSchema
from ..infrabackend.repository import StoreRepository, ProductRepository
from ..infrabackend.database import SessionLocal
from ..domain.models import Platform, Store

logger = logging.getLogger(__name__)


class Extractor:

    def __init__(self):
        # Sessão criada aqui — fechada no finally de cada método público
        self.db       = SessionLocal()
        self.dbStore   = StoreRepository(db=self.db)
        self.dbProduct = ProductRepository(db=self.db)

    def _close(self):
        self.db.close()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _sha256_id(brand: str, slug: str, size: str) -> int:
        """ID determinístico — mesmo resultado em qualquer processo."""
        key    = f"{brand}|{slug}|{size}".lower()
        digest = hashlib.sha256(key.encode()).hexdigest()
        return int(digest[:16], 16) % (10 ** 10)

    @staticmethod
    def _parse_price(text: str) -> float | None:
        clean = re.sub(r"[^\d,]", "", text)
        if not clean:
            return None
        try:
            return float(clean.replace(",", "."))
        except ValueError:
            return None

    def _get_or_create_store(self, brand: str, url: str, platform: Platform) -> Store:
        """
        Retorna a store existente ou cria uma nova.
        Chamado UMA vez por brand, não por variante.
        """
        store = self.dbStore.get_by_brand(brand)
        if not store:
            store = Store(brand=brand, url=url, platform=platform)
            self.db.add(store)
            self.db.flush()
            logger.info("Nova loja criada: %s", brand)
        return store


    def shopify(self, urls: dict = SHOPIFY_URLS):
        try:
            for brand, url in urls.items():
                self._extract_shopify_brand(brand, url)
            self.db.commit()
            logger.info("Shopify: commit realizado com sucesso")
        except Exception as e:
            self.db.rollback()
            logger.error("Shopify: erro no commit — %s", e)
            raise
        finally:
            self._close()

    def _extract_shopify_brand(self, brand: str, url: str):
        logger.info("[Shopify] Iniciando: %s", brand)

        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.error("[Shopify] Falha ao buscar %s: %s", brand, e)
            return

        store = self._get_or_create_store(brand, url, Platform.shopify)
        saved = 0

        for item in data.get("products", []):
            images    = item.get("images") or []
            image     = images[0].get("src") if images else None
            base_link = url.replace("/products.json?limit=250", f"/products/{item['handle']}")

            for variant in item.get("variants", []):
                try:
                    discount_price = float(variant.get("price") or 0)
                    if discount_price <= 0:
                        continue

                    raw_compare   = variant.get("compare_at_price")
                    compare_price = float(raw_compare) if raw_compare else None
                    full_price    = (
                        compare_price
                        if compare_price and compare_price > discount_price
                        else discount_price
                    )

                    schema = ProductSchema(
                        brand          = brand,
                        name           = item["title"],
                        clothing_id    = int(variant["id"]),
                        discount_price = discount_price,
                        full_price     = full_price,
                        available      = variant.get("available", False),
                        size           = variant.get("title", "Único"),
                        link           = base_link,
                        image          = image,
                    )

                    self.dbProduct.upsert(schema=schema, brand=brand)
                    saved += 1

                except Exception as e:
                    logger.warning(
                        "[Shopify] Variante ignorada brand=%s name=%s: %s",
                        brand, item.get("title"), e
                    )

        logger.info("[Shopify] %s: %d variantes processadas", brand, saved)

    # ── NuvemShop ──────────────────────────────────────────────────────────────

    def nuvemshop(self, urls: dict = NUVEMSHOP_URLS):
        try:
            for brand, base_url in urls.items():
                self._extract_nuvemshop_brand(brand, base_url)
            self.db.commit()
            logger.info("NuvemShop: commit realizado com sucesso")
        except Exception as e:
            self.db.rollback()
            logger.error("NuvemShop: erro no commit — %s", e)
            raise
        finally:
            self._close()

    def _extract_nuvemshop_brand(self, brand: str, base_url: str):
        logger.info("[NuvemShop] Iniciando: %s", brand)

        base_url     = base_url.rstrip("/")
        products_url = f"{base_url}/produtos/"
        

        # Garante que a store existe — UMA vez por brand, fora do loop
        store = self._get_or_create_store(brand, base_url, Platform.nuvemshop)

        page      = 1
        processed = 0

        with httpx.Client(timeout=10, follow_redirects=True) as client:
            while page <= 20:
                try:
                    if "wanted" in base_url:
                        products_url = f"{base_url}/loja/"
                        response = client.get(f"{products_url}")
                        response.raise_for_status()
                    elif "basyc" in base_url:
                        products_url = f"{base_url}/"
                        response = client.get(f"{products_url}")
                        response.raise_for_status()
                    else:
                        response = client.get(f"{products_url}?page={page}")
                        response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        break
                    logger.error("[NuvemShop] HTTP erro página %d de %s: %s", page, brand, e)
                    break
                except Exception as e:
                    logger.error("[NuvemShop] Erro página %d de %s: %s", page, brand, e)
                    break

                soup          = BeautifulSoup(response.text, "html.parser")
                product_links = self._extract_slugs(soup)

                if not product_links:
                    break

                for slug, href in product_links:
                    count = self._process_nuvemshop_product(
                        client, brand, base_url, slug, href, store
                    )
                    processed += count

                next_link = soup.select_one("a.next, a[rel='next'], .pagination-next")
                if not next_link:
                    break

                page += 1

        logger.info("[NuvemShop] %s: %d variantes processadas", brand, processed)

    def _extract_slugs(self, soup: BeautifulSoup) -> list[tuple[str, str]]:
        items = soup.select(".item-product, .product-item, [itemtype*='Product']")
        links = items if items else soup.select("a[href*='/produtos/']")

        seen, slugs = set(), []
        for el in links:
            tag  = el if el.name == "a" else el.select_one("a[href*='/produtos/']")
            href = tag.get("href", "") if tag else ""
            m    = re.search(r"/produtos/([a-z0-9\-]+)/?$", href)
            if m and m.group(1) not in seen:
                seen.add(m.group(1))
                slugs.append((m.group(1), href))
        return slugs

    def _process_nuvemshop_product(
        self,
        client:   httpx.Client,
        brand:    str,
        base_url: str,
        slug:     str,
        href:     str,
        store:    Store,
    ) -> int:
        product_url = href if href.startswith("http") else f"{base_url}{href}"

        try:
            resp = client.get(product_url)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("[NuvemShop] Falha ao buscar %s/%s: %s", brand, slug, e)
            return 0

        soup = BeautifulSoup(resp.text, "html.parser")

        # Nome
        name_el = soup.select_one("h1.product-name, h1[itemprop='name'], .product-title h1, h1")
        name    = name_el.get_text(strip=True) if name_el else slug.replace("-", " ").title()

        # Preço
        discount_price = None
        for selector in ["span.price-amount", "span[itemprop='price']",
                         ".product-price span", "#price_display", ".js-price-display"]:
            el = soup.select_one(selector)
            if el:
                discount_price = self._parse_price(el.get_text(strip=True))
                if discount_price:
                    break

        if not discount_price:
            logger.debug("[NuvemShop] Preço não encontrado: %s/%s", brand, slug)
            return 0

        # Preço cheio
        full_price  = discount_price
        compare_el  = soup.select_one(".price-compare, .compare-at-price, del, s")
        if compare_el:
            compare = self._parse_price(compare_el.get_text(strip=True))
            if compare and compare > discount_price:
                full_price = compare

        # Imagem
        image  = None
        img_el = soup.select_one(".product-image img, img[itemprop='image'], .js-product-slide-img")
        if img_el:
            image = img_el.get("data-src") or img_el.get("src")
            if image and image.startswith("//"):
                image = "https:" + image

        # Variantes
        variants   = []
        select_el  = soup.select_one("select.js-variation-option, select[name*='variation']")
        if select_el:
            for opt in select_el.find_all("option"):
                text = opt.get_text(strip=True)
                if text and text.lower() not in ("selecione", "escolha", ""):
                    variants.append({
                        "size":      text,
                        "available": not bool(opt.get("disabled")),
                    })
        if not variants:
            variants = [{"size": "Único", "available": True}]

        saved = 0
        for variant in variants:
            try:
                schema = ProductSchema(
                    brand          = brand,
                    name           = name,
                    clothing_id    = self._sha256_id(brand, slug, variant["size"]),
                    discount_price = discount_price,
                    full_price     = full_price,
                    available      = variant["available"],
                    size           = variant["size"],
                    link           = product_url,
                    image          = image,
                )
                self.dbProduct.upsert(schema=schema, brand=brand)
                saved += 1
            except Exception as e:
                logger.warning("[NuvemShop] Variante ignorada %s/%s: %s", brand, name, e)

        return saved


