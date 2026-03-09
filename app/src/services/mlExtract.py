import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

from ..infrabackend.database import SessionLocal
from ..infrabackend.config import ML_CATEGORIES, ML_BASE_URL
from ..domain.models import MLProduct

logger = logging.getLogger(__name__)


MIN_DISCOUNT_PCT = 10.0
_PAGE_DELAY      = 1.0   # segundos entre páginas

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_price(el) -> float | None:
    """
    Extrai preço de .andes-money-amount.
    Estrutura: __fraction (inteiro) + __cents (centavos, opcional).
    """
    if el is None:
        return None
    fraction_el = el.select_one(".andes-money-amount__fraction")
    cents_el    = el.select_one(".andes-money-amount__cents")
    if not fraction_el:
        return None
    try:
        inteiro = int(fraction_el.get_text(strip=True).replace(".", "").replace(",", ""))
        cents   = 0
        if cents_el:
            c = cents_el.get_text(strip=True).replace(",", "").replace(".", "")
            cents = int(c) if c.isdigit() else 0
        return float(inteiro) + cents / 100
    except (ValueError, AttributeError):
        return None


def _fix_image(url: str | None) -> str | None:
    """
    Converte thumbnail de listagem para imagem full-size.
    ML usa sufixos: -E (thumbnail tiny), -O (original full), -B (800px).
    Troca qualquer sufixo de letra única antes de .webp por -O.
    Ex: ...MLB123-E.webp  →  ...MLB123-O.webp
    """
    if not url:
        return None
    return re.sub(r"-[A-Z]\.webp$", "-O.webp", url)


def _extract_item_id(link: str, image: str | None = None) -> str | None:
    """
    Extrai o MLB... de forma confiável.
    Ordem: imagem (mais confiável) → link.
    """
    for text in filter(None, [image, link]):
        m = re.search(r"MLB-?\d+", text)
        if m:
            return m.group(0).replace("-", "")
    return None


def _clean_link(item_id: str) -> str:
    """
    Monta permalink limpo direto do item_id.
    Evita salvar URLs de tracking com 700+ chars.
    """
    return f"https://www.mercadolivre.com.br/p/{item_id}"


# ── Extrator ──────────────────────────────────────────────────────────────────

class MLExtractor:
    """
    scrapper de produtos com desconto do ML e salva em ml_products.

    Parâmetros
    ----------
    min_discount_pct  : desconto mínimo em % (padrão: 10)
    max_per_category  : limite de produtos por categoria (padrão: 100)
    categories        : dict {label: slug}; usa ML_TECH_CATEGORIES por padrão
    """

    def __init__(
        self,
        min_discount_pct: float = MIN_DISCOUNT_PCT,
        max_per_category: int   = 1000,
        categories: dict[str, str] | None = None,
    ):
        self.min_discount_pct = min_discount_pct
        self.max_per_category = max_per_category
        self.categories       = categories or ML_CATEGORIES
        self.db               = SessionLocal()

    def _close(self) -> None:
        self.db.close()

    # ── Paginação ─────────────────────────────────────────────────────────────

    def _page_url(self, slug: str, offset: int) -> str:
        if offset == 0:
            return f"{ML_BASE_URL}/{slug}"
        return f"{ML_BASE_URL}/{slug}_Desde_{offset + 1}_NoIndex_True"

    # ── Parsing ───────────────────────────────────────────────────────────────

    def _parse_items(self, soup: BeautifulSoup) -> list[dict]:
        """
        Seletores validados no HTML real (março 2025):
          li.ui-search-layout__item
            a.poly-component__title            → título + link
            s.andes-money-amount--previous     → preço original riscado
            div.poly-price__current            → preço com desconto
            img.poly-component__picture        → imagem (src ou data-src)
        """
        results = []

        for card in soup.select("li.ui-search-layout__item"):
            try:
                # Título + link
                title_el = card.select_one("a.poly-component__title")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                link  = title_el.get("href", "").split("#")[0]

                # Preço original riscado — sem ele não há desconto real
                original = _parse_price(card.select_one("s.andes-money-amount--previous"))
                if not original:
                    continue

                # Preço atual — último .andes-money-amount dentro de .poly-price__current
                # que não seja o elemento riscado
                price = None
                container = card.select_one("div.poly-price__current")
                if container:
                    valid = [
                        el for el in container.select(".andes-money-amount")
                        if "andes-money-amount--previous" not in el.get("class", [])
                        and el.find("s") is None
                    ]
                    if valid:
                        price = _parse_price(valid[-1])

                if not price or price <= 0 or original <= price:
                    continue

                disc = round((1 - price / original) * 100, 2)

                # Imagem — data-src (lazy load) ou src; converte para full-size
                img_el = card.select_one("img.poly-component__picture")
                image  = None
                if img_el:
                    raw   = img_el.get("data-src") or img_el.get("src")
                    image = _fix_image(raw)

                # Extrai ID do MLB a partir da imagem (mais confiável que o link de tracking)
                item_id = _extract_item_id(link, image)
                if not item_id:
                    logger.debug("[ML] item_id nao encontrado, descartando: %s", title[:50])
                    continue

                results.append({
                    "item_id":  item_id,
                    "title":    title,
                    "price":    price,
                    "original": original,
                    "discount": disc,
                    "link":     _clean_link(item_id),
                    "image":    image,
                })

            except Exception as exc:
                logger.debug("[ML] Erro ao parsear card: %s", exc)

        return results

    # ── Upsert ────────────────────────────────────────────────────────────────

    def _upsert(self, item: dict, category: str) -> None:
        """Insere ou atualiza um MLProduct pelo ml_item_id."""
        try:
            existing = (
                self.db.query(MLProduct)
                .filter(MLProduct.ml_item_id == item["item_id"])
                .first()
            )
            if existing:
                existing.discount_price = item["price"]
                existing.full_price     = item["original"]
                existing.discount_pct   = item["discount"]
                existing.image          = item["image"]
                existing.link           = item["link"]
            else:
                self.db.add(MLProduct(
                    ml_item_id     = item["item_id"],
                    category       = category,
                    title          = item["title"],
                    discount_price = item["price"],
                    full_price     = item["original"],
                    discount_pct   = item["discount"],
                    image          = item["image"],
                    link           = item["link"],
                ))
            self.db.flush()
        except Exception:
            # Rollback local — libera a session para o próximo item
            self.db.rollback()
            raise

    # ── Extração por categoria ────────────────────────────────────────────────

    def _extract_category(self, category: str, slug: str, client: httpx.Client) -> int:
        logger.info("[ML] Iniciando: %s", category)
        saved  = 0
        offset = 0

        while saved < self.max_per_category:
            url = self._page_url(slug, offset)
            try:
                resp = client.get(url, headers=_HEADERS, timeout=20)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    logger.info("[ML] %s: fim da paginação (offset %d)", category, offset)
                else:
                    logger.error("[ML] HTTP %s em %s offset %d", exc.response.status_code, category, offset)
                break
            except Exception as exc:
                logger.error("[ML] Erro em %s offset %d: %s", category, offset, exc)
                break

            items = self._parse_items(BeautifulSoup(resp.text, "html.parser"))
            if not items:
                logger.info("[ML] %s: sem itens na página (offset %d)", category, offset)
                break

            for item in items:
                if item["discount"] < self.min_discount_pct:
                    continue
                try:
                    self._upsert(item, category)
                    saved += 1
                except Exception as exc:
                    logger.warning("[ML] Item ignorado %s: %s", item.get("item_id"), exc)
                if saved >= self.max_per_category:
                    break

            offset += 48
            time.sleep(_PAGE_DELAY)

        logger.info("[ML] %s: %d produtos salvos (desc >= %.0f%%)", category, saved, self.min_discount_pct)
        return saved

    # ── Método público ────────────────────────────────────────────────────────

    def extract(self, categories: dict[str, str] | None = None) -> None:
        cats = categories or self.categories
        try:
            with httpx.Client(follow_redirects=True, timeout=20) as client:
                for category, slug in cats.items():
                    self._extract_category(category, slug, client)
            self.db.commit()
            logger.info("[ML] Commit realizado com sucesso")
        except Exception as exc:
            self.db.rollback()
            logger.error("[ML] Erro no commit: %s", exc)
            raise
        finally:
            self._close()