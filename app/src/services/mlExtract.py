import logging
import random
import re
import time
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from ..infrabackend.database import SessionLocal
from ..infrabackend.config import ML_CATEGORIES, ML_BASE_URL
from ..domain.models import MLProduct

logger = logging.getLogger(__name__)

MIN_DISCOUNT_PCT = 10.0
_PAGE_DELAY      = 1.0   # segundos entre páginas
_REQUEST_TIMEOUT = 20.0
_MAX_PAGE_RETRIES = 4
_WARMUP_DELAY = 0.5
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}

_CLIENT_PROFILES = [
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
    },
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) "
            "Gecko/20100101 Firefox/124.0"
        ),
    },
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
        ),
        "Sec-CH-UA": '"Microsoft Edge";v="124", "Chromium";v="124", "Not-A.Brand";v="99"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
    },
]

_BLOCK_MARKERS = (
    "captcha",
    "recaptcha",
    "verify",
    "verification",
    "valide",
    "validar",
    "verifique",
    "atividade incomum",
    "atividade suspeita",
    "access denied",
    "security challenge",
    "sou humano",
    "já tenho conta",
    "ja tenho conta",
    "possuo conta",
    "iniciar sessão",
    "iniciar sessao",
)

_GATE_ACTION_MARKERS = (
    "já tenho conta",
    "ja tenho conta",
    "possuo conta",
    "iniciar sessão",
    "iniciar sessao",
    "continuar",
    "entrar",
)

_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
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

class MLTemporaryBlock(Exception):
    def __init__(self, message: str, redirect_url: str | None = None):
        super().__init__(message)
        self.redirect_url = redirect_url


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
        self._client_seed     = random.randint(0, len(_CLIENT_PROFILES) - 1)

    def _close(self) -> None:
        self.db.close()

    def _client_headers(self, profile_index: int, referer: str | None = None) -> dict[str, str]:
        headers = dict(_HEADERS)
        headers.update(_CLIENT_PROFILES[profile_index % len(_CLIENT_PROFILES)])
        if referer:
            headers["Referer"] = referer
        return headers

    def _new_client(self, profile_index: int) -> httpx.Client:
        return httpx.Client(
            follow_redirects=False,
            timeout=_REQUEST_TIMEOUT,
            http2=True,
            headers=self._client_headers(profile_index),
        )

    def _looks_blocked(self, response: httpx.Response) -> bool:
        if response.status_code in _REDIRECT_STATUSES:
            return True

        location = (response.headers.get("location") or "").lower()
        if location and any(marker in location for marker in _BLOCK_MARKERS):
            return True

        page_url = str(response.url).lower()
        if any(marker in page_url for marker in _BLOCK_MARKERS):
            return True

        body = response.text.lower()
        return any(marker in body for marker in _BLOCK_MARKERS)

    def _raise_if_blocked(self, response: httpx.Response) -> None:
        if not self._looks_blocked(response):
            return

        redirect_url = response.headers.get("location")
        message = f"bloqueio detectado (status={response.status_code})"
        raise MLTemporaryBlock(message, redirect_url=redirect_url)

    def _warmup_client(self, client: httpx.Client, slug: str, profile_index: int) -> None:
        warmup_urls = [
            "https://www.mercadolivre.com.br/",
            ML_BASE_URL,
            f"{ML_BASE_URL}/{slug}",
        ]

        referer = "https://www.google.com/"
        for warmup_url in warmup_urls:
            try:
                response = client.get(
                    warmup_url,
                    headers=self._client_headers(profile_index, referer=referer),
                    timeout=_REQUEST_TIMEOUT,
                )
                if response.status_code not in _REDIRECT_STATUSES:
                    referer = str(response.url)
                time.sleep(random.uniform(0.15, _WARMUP_DELAY))
            except Exception:
                continue

    def _submit_gate_candidate(self, client: httpx.Client, gate_response: httpx.Response, candidate_url: str) -> None:
        try:
            client.get(
                candidate_url,
                headers={**dict(client.headers), "Referer": str(gate_response.url)},
                timeout=_REQUEST_TIMEOUT,
                follow_redirects=True,
            )
        except Exception:
            return

    def _try_gate_actions(self, client: httpx.Client, gate_response: httpx.Response) -> None:
        soup = BeautifulSoup(gate_response.text, "html.parser")

        for anchor in soup.select("a[href]"):
            label = " ".join(filter(None, [anchor.get_text(" ", strip=True), anchor.get("title"), anchor.get("aria-label")])).lower()
            href = anchor.get("href")
            if not href or not any(marker in label for marker in _GATE_ACTION_MARKERS):
                continue
            self._submit_gate_candidate(client, gate_response, urljoin(str(gate_response.url), href))

        for form in soup.select("form"):
            label = " ".join(form.stripped_strings).lower()
            if not any(marker in label for marker in _GATE_ACTION_MARKERS):
                continue

            action = urljoin(str(gate_response.url), form.get("action") or str(gate_response.url))
            method = (form.get("method") or "get").strip().lower()
            data = {
                field.get("name"): field.get("value", "")
                for field in form.select("input[name]")
                if field.get("name")
            }

            try:
                if method == "post":
                    client.post(
                        action,
                        data=data,
                        headers={**dict(client.headers), "Referer": str(gate_response.url)},
                        timeout=_REQUEST_TIMEOUT,
                        follow_redirects=True,
                    )
                else:
                    client.get(
                        action,
                        params=data,
                        headers={**dict(client.headers), "Referer": str(gate_response.url)},
                        timeout=_REQUEST_TIMEOUT,
                        follow_redirects=True,
                    )
            except Exception:
                continue

    def _attempt_unblock(self, client: httpx.Client, blocked_url: str | None, referer: str) -> None:
        if not blocked_url:
            return

        target_url = urljoin(referer, blocked_url)
        try:
            gate_response = client.get(
                target_url,
                headers={**dict(client.headers), "Referer": referer},
                timeout=_REQUEST_TIMEOUT,
                follow_redirects=True,
            )
        except Exception:
            return

        self._try_gate_actions(client, gate_response)

    def _fetch_page(self, client: httpx.Client, url: str, profile_index: int, referer: str) -> httpx.Response:
        response = client.get(
            url,
            headers=self._client_headers(profile_index, referer=referer),
            timeout=_REQUEST_TIMEOUT,
        )
        self._raise_if_blocked(response)
        response.raise_for_status()
        return response

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

    def _extract_category(self, category: str, slug: str) -> int:
        logger.info("[ML] Iniciando: %s", category)
        saved  = 0
        offset = 0
        profile_index = self._client_seed
        client = self._new_client(profile_index)
        self._warmup_client(client, slug, profile_index)

        try:
            while saved < self.max_per_category:
                url = self._page_url(slug, offset)
                referer = f"{ML_BASE_URL}/{slug}"
                resp = None

                for attempt in range(_MAX_PAGE_RETRIES):
                    try:
                        resp = self._fetch_page(client, url, profile_index, referer=referer)
                        break
                    except MLTemporaryBlock as exc:
                        logger.warning(
                            "[ML] Bloqueio em %s offset %d tentativa %d/%d",
                            category,
                            offset,
                            attempt + 1,
                            _MAX_PAGE_RETRIES,
                        )
                        self._attempt_unblock(client, exc.redirect_url, referer=referer)
                    except httpx.TimeoutException:
                        logger.warning(
                            "[ML] Timeout em %s offset %d tentativa %d/%d",
                            category,
                            offset,
                            attempt + 1,
                            _MAX_PAGE_RETRIES,
                        )
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code == 404:
                            logger.info("[ML] %s: fim da paginação (offset %d)", category, offset)
                            return saved
                        logger.warning(
                            "[ML] HTTP %s em %s offset %d tentativa %d/%d",
                            exc.response.status_code,
                            category,
                            offset,
                            attempt + 1,
                            _MAX_PAGE_RETRIES,
                        )
                    except Exception as exc:
                        logger.warning(
                            "[ML] Erro em %s offset %d tentativa %d/%d: %s",
                            category,
                            offset,
                            attempt + 1,
                            _MAX_PAGE_RETRIES,
                            exc,
                        )

                    try:
                        client.close()
                    except Exception:
                        pass

                    profile_index += 1
                    client = self._new_client(profile_index)
                    self._warmup_client(client, slug, profile_index)
                    time.sleep((2 ** attempt) + random.uniform(0.25, 1.0))

                if resp is None:
                    logger.error("[ML] Falha persistente em %s offset %d", category, offset)
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
                time.sleep(_PAGE_DELAY + random.uniform(0.1, 0.6))
        finally:
            client.close()

        logger.info("[ML] %s: %d produtos salvos (desc >= %.0f%%)", category, saved, self.min_discount_pct)
        return saved

    # ── Método público ────────────────────────────────────────────────────────

    def extract(self, categories: dict[str, str] | None = None) -> None:
        cats = categories or self.categories
        try:
            for category, slug in cats.items():
                self._extract_category(category, slug)
            self.db.commit()
            logger.info("[ML] Commit realizado com sucesso")
        except Exception as exc:
            self.db.rollback()
            logger.error("[ML] Erro no commit: %s", exc)
            raise
        finally:
            self._close()