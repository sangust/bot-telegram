"""
MLExtractor — scraping HTML de produtos com desconto do Mercado Livre.

Estratégia anti-bloqueio:
  - Proxy rotation (ML_PROXY_URLS env var)
  - User-Agent rotation entre perfis Chrome/Firefox/Edge
  - Warmup de sessão antes de cada categoria
  - Detecção de redirect 302 e páginas de verificação
  - Tentativa automática de clicar "já tenho conta" em gates
  - Retry com backoff exponencial + troca de proxy/UA
  - Delay humanizado com jitter entre páginas
"""

import logging
import random
import re
import time
import unicodedata
from urllib.parse import urljoin, quote

import httpx
from bs4 import BeautifulSoup

from ..infrabackend.database import SessionLocal
from ..infrabackend.config import (
    ML_CATEGORIES, ML_BASE_URL, ML_MIN_DISCOUNT, ML_MAX_PER_CAT, PROXY_URLS,
)
from ..domain.models import MLProduct

logger = logging.getLogger(__name__)

_PAGE_DELAY       = 1.0
_REQUEST_TIMEOUT  = 20.0
_MAX_PAGE_RETRIES = 3
_REDIRECT_CODES   = {301, 302, 303, 307, 308}

_UA_PROFILES = [
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Sec-CH-UA": '"Chromium";v="125", "Google Chrome";v="125", "Not-A.Brand";v="99"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
    },
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) "
            "Gecko/20100101 Firefox/126.0"
        ),
    },
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0"
        ),
        "Sec-CH-UA": '"Microsoft Edge";v="125", "Chromium";v="125", "Not-A.Brand";v="99"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
    },
]

_BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}

_BLOCK_MARKERS = (
    "captcha", "recaptcha", "verify", "verification",
    "valide", "validar", "verifique",
    "atividade incomum", "atividade suspeita",
    "access denied", "security challenge", "sou humano",
    "já tenho conta", "ja tenho conta", "possuo conta",
    "iniciar sessão", "iniciar sessao",
)

_GATE_MARKERS = (
    "já tenho conta", "ja tenho conta", "possuo conta",
    "iniciar sessão", "iniciar sessao", "continuar", "entrar",
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_price(el) -> float | None:
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
    if not url:
        return None
    return re.sub(r"-[A-Z]\.webp$", "-O.webp", url)


def _extract_item_id(link: str, image: str | None = None) -> str | None:
    for text in filter(None, [image, link]):
        m = re.search(r"MLB-?\d+", text)
        if m:
            return m.group(0).replace("-", "")
    return None


def _clean_link(item_id: str) -> str:
    return f"https://www.mercadolivre.com.br/p/{item_id}"


def _slug_to_url(slug: str) -> str:
    return f"{ML_BASE_URL}/{_slug_to_path(slug)}"


def _slug_to_path(slug: str) -> str:
    normalized = unicodedata.normalize("NFKD", slug).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return normalized


class _BlockDetected(Exception):
    def __init__(self, redirect_url: str | None = None):
        super().__init__("bloqueio detectado")
        self.redirect_url = redirect_url


# ── Proxy + Client manager ───────────────────────────────────────────────────

class _ClientFactory:
    def __init__(self, proxies: list[str]) -> None:
        self._proxies = proxies if proxies else [None]
        self._ua_index = random.randint(0, len(_UA_PROFILES) - 1)
        self._proxy_index = random.randint(0, max(len(self._proxies) - 1, 0))

    def _next_profile(self) -> dict[str, str]:
        self._ua_index += 1
        return _UA_PROFILES[self._ua_index % len(_UA_PROFILES)]

    def _next_proxy(self) -> str | None:
        self._proxy_index += 1
        return self._proxies[self._proxy_index % len(self._proxies)]

    @staticmethod
    def _normalize_proxy(proxy: str | None) -> str | None:
        if not proxy:
            return None
        candidate = proxy.strip()
        if candidate.startswith("https://"):
            return "http://" + candidate.removeprefix("https://")
        return candidate

    def build_headers(self, referer: str | None = None) -> dict[str, str]:
        headers = dict(_BASE_HEADERS)
        headers.update(_UA_PROFILES[self._ua_index % len(_UA_PROFILES)])
        if referer:
            headers["Referer"] = referer
        return headers

    def new_client(self, force_direct: bool = False) -> httpx.Client:
        proxy = None if force_direct else self._normalize_proxy(self._next_proxy())
        self._next_profile()
        kwargs: dict = {
            "follow_redirects": False,
            "timeout": _REQUEST_TIMEOUT,
            "http2": True,
            "trust_env": False,
        }
        if proxy:
            kwargs["proxy"] = proxy
        return httpx.Client(**kwargs)


# ── Extrator ──────────────────────────────────────────────────────────────────

class MLExtractor:
    def __init__(
        self,
        min_discount_pct: float = ML_MIN_DISCOUNT,
        max_per_category: int   = ML_MAX_PER_CAT,
        categories: dict[str, str] | None = None,
        proxies: list[str] | None = None,
    ) -> None:
        self.min_discount_pct = min_discount_pct
        self.max_per_category = max_per_category
        self.categories       = categories or ML_CATEGORIES
        self.db               = SessionLocal()
        self._factory         = _ClientFactory(proxies if proxies is not None else PROXY_URLS)

    def _close(self) -> None:
        self.db.close()

    # ── Detecção de bloqueio ───────────────────────────────────────────────

    @staticmethod
    def _looks_blocked(resp: httpx.Response) -> bool:
        if resp.status_code in _REDIRECT_CODES:
            return True
        body = resp.text[:5000].lower()
        return any(m in body for m in _BLOCK_MARKERS)

    def _raise_if_blocked(self, resp: httpx.Response) -> None:
        if self._looks_blocked(resp):
            raise _BlockDetected(redirect_url=resp.headers.get("location"))

    # ── Gate bypass ────────────────────────────────────────────────────────

    def _try_gate_bypass(self, client: httpx.Client, resp: httpx.Response) -> None:
        soup = BeautifulSoup(resp.text, "html.parser")
        base = str(resp.url)

        for anchor in soup.select("a[href]"):
            label = anchor.get_text(" ", strip=True).lower()
            href = anchor.get("href")
            if not href or not any(m in label for m in _GATE_MARKERS):
                continue
            try:
                client.get(
                    urljoin(base, href),
                    headers=self._factory.build_headers(referer=base),
                    follow_redirects=True,
                )
            except Exception:
                pass
            return

        for form in soup.select("form"):
            label = " ".join(form.stripped_strings).lower()
            if not any(m in label for m in _GATE_MARKERS):
                continue
            action = urljoin(base, form.get("action") or base)
            method = (form.get("method") or "get").strip().lower()
            data = {
                f.get("name"): f.get("value", "")
                for f in form.select("input[name]") if f.get("name")
            }
            try:
                if method == "post":
                    client.post(action, data=data, headers=self._factory.build_headers(referer=base), follow_redirects=True)
                else:
                    client.get(action, params=data, headers=self._factory.build_headers(referer=base), follow_redirects=True)
            except Exception:
                pass
            return

    # ── Warmup ─────────────────────────────────────────────────────────────

    def _warmup(self, client: httpx.Client) -> None:
        referer = "https://www.google.com/"
        for url in ["https://www.mercadolivre.com.br/", ML_BASE_URL]:
            try:
                r = client.get(url, headers=self._factory.build_headers(referer=referer))
                if r.status_code not in _REDIRECT_CODES:
                    referer = str(r.url)
                time.sleep(random.uniform(0.2, 0.5))
            except Exception:
                pass

    # ── Fetch com retry ────────────────────────────────────────────────────

    def _fetch_page(self, url: str, slug: str) -> tuple[httpx.Response, httpx.Client]:
        referer = self._page_url(slug, 0)
        direct_mode = True
        client = self._factory.new_client(force_direct=direct_mode)
        self._warmup(client)

        for attempt in range(_MAX_PAGE_RETRIES):
            try:
                resp = client.get(url, headers=self._factory.build_headers(referer=referer))
                if resp.status_code in _REDIRECT_CODES:
                    redirect_url = resp.headers.get("location")
                    if redirect_url and "mercadolivre.com.br" in redirect_url:
                        resp = client.get(
                            urljoin(str(resp.url), redirect_url),
                            headers=self._factory.build_headers(referer=referer),
                        )
                self._raise_if_blocked(resp)
                resp.raise_for_status()
                return resp, client
            except _BlockDetected as exc:
                logger.warning("[ML] Bloqueio em %s tentativa %d/%d", url[:80], attempt + 1, _MAX_PAGE_RETRIES)
                if direct_mode and any(self._factory._proxies):
                    direct_mode = False
                    logger.warning("[ML] Repetindo com proxy após bloqueio em conexão direta")
                if exc.redirect_url:
                    try:
                        gate = client.get(
                            urljoin(referer, exc.redirect_url),
                            headers=self._factory.build_headers(referer=referer),
                            follow_redirects=True,
                        )
                        self._try_gate_bypass(client, gate)
                    except Exception:
                        pass
            except httpx.TimeoutException:
                logger.warning("[ML] Timeout em %s tentativa %d/%d", url[:80], attempt + 1, _MAX_PAGE_RETRIES)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    raise
                logger.warning("[ML] HTTP %s em %s tentativa %d/%d", exc.response.status_code, url[:80], attempt + 1, _MAX_PAGE_RETRIES)
            except Exception as exc:
                logger.warning("[ML] Erro em %s tentativa %d/%d: %s", url[:80], attempt + 1, _MAX_PAGE_RETRIES, exc)
                if "WRONG_VERSION_NUMBER" in str(exc) and not direct_mode:
                    direct_mode = True
                    logger.warning("[ML] Proxy TLS inválido em %s; repetindo sem proxy", url[:80])

            try:
                client.close()
            except Exception:
                pass
            client = self._factory.new_client(force_direct=direct_mode)
            self._warmup(client)
            time.sleep((2 ** attempt) + random.uniform(0.3, 1.2))

        raise RuntimeError(f"Falha persistente após {_MAX_PAGE_RETRIES} tentativas: {url[:80]}")

    # ── Parsing HTML ───────────────────────────────────────────────────────

    def _parse_items(self, soup: BeautifulSoup) -> list[dict]:
        results = []
        for card in soup.select("li.ui-search-layout__item"):
            try:
                title_el = card.select_one("a.poly-component__title")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                link  = title_el.get("href", "").split("#")[0]

                original = _parse_price(card.select_one("s.andes-money-amount--previous"))
                if not original:
                    continue

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

                img_el = card.select_one("img.poly-component__picture")
                image  = None
                if img_el:
                    raw = img_el.get("data-src") or img_el.get("src")
                    image = _fix_image(raw)

                item_id = _extract_item_id(link, image)
                if not item_id:
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

    # ── Paginação ──────────────────────────────────────────────────────────

    def _page_url(self, slug: str, offset: int) -> str:
        encoded = _slug_to_path(slug)
        if offset == 0:
            return f"{ML_BASE_URL}/{encoded}"
        return f"{ML_BASE_URL}/{encoded}_Desde_{offset + 1}_NoIndex_True"

    # ── Upsert ─────────────────────────────────────────────────────────────

    def _upsert(self, item: dict, category: str) -> None:
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
                existing.title          = item["title"]
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
            self.db.rollback()
            raise

    # ── Extração por categoria ─────────────────────────────────────────────

    def _extract_category(self, category: str, slug: str) -> int:
        logger.info("[ML] Iniciando: %s (slug=%s)", category, slug)
        saved  = 0
        offset = 0

        while saved < self.max_per_category:
            url = self._page_url(slug, offset)
            try:
                resp, client = self._fetch_page(url, slug)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    logger.info("[ML] %s: fim da paginação (offset %d)", category, offset)
                break
            except RuntimeError:
                logger.error("[ML] Falha persistente em %s offset %d — parando categoria", category, offset)
                break

            try:
                items = self._parse_items(BeautifulSoup(resp.text, "html.parser"))
            finally:
                client.close()

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
            time.sleep(_PAGE_DELAY + random.uniform(0.2, 0.8))

        logger.info("[ML] %s: %d produtos salvos (desc >= %.0f%%)", category, saved, self.min_discount_pct)
        return saved

    # ── Método público ─────────────────────────────────────────────────────

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