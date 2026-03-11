import ast
import os
from pathlib import Path
from dotenv import load_dotenv

#carrega as variavel de ambiente (.env)
load_dotenv()


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Variável de ambiente obrigatória ausente: {name}")
    return value.strip()


def _optional_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _normalize_proxies(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        candidate = value.strip().strip('"').strip("'")
        if candidate.startswith(("http://", "https://", "socks5://", "socks5h://")):
            normalized.append(candidate)
    return normalized


def _parse_proxy_urls(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []

    text = raw_value.strip()
    if not text:
        return []

    if text.startswith("["):
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            parsed = None
        if isinstance(parsed, (list, tuple)):
            return _normalize_proxies([str(item) for item in parsed])

    if "," in text:
        return _normalize_proxies(text.split(","))

    return _normalize_proxies([text])


def _load_proxy_urls() -> list[str]:
    proxies = _parse_proxy_urls(_optional_env("ML_PROXY_URLS", ""))
    if proxies:
        return proxies

    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return []

    lines = env_path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        if key.strip() != "ML_PROXY_URLS":
            continue

        buffer = raw_value.strip()
        if buffer.startswith("[") and not buffer.rstrip().endswith("]"):
            parts = [buffer]
            for next_line in lines[index + 1:]:
                parts.append(next_line.strip())
                if next_line.strip().endswith("]"):
                    break
            buffer = "\n".join(parts)

        return _parse_proxy_urls(buffer)

    return []

#banco de dados
DATABASE_URL = _required_env("DATABASE_URL")

#bot token telegram
BOT_TOKENS = [
    token
    for token in [
        _optional_env("BOT_TOKEN_1"),
        _optional_env("BOT_TOKEN_2"),
        _optional_env("BOT_TOKEN_3"),
    ]
    if token
]

BOT_TOKEN_ALIASES = {
    f"bot{index}": token
    for index, token in enumerate(BOT_TOKENS, start=1)
}
BOT_TOKEN_BY_VALUE = {
    token: alias
    for alias, token in BOT_TOKEN_ALIASES.items()
}

#url do site em prod ou dev
BASE_URL = _required_env("BASE_URL")

#chave para cookie de sessao
SECRET_KEY = _required_env("SECRET_KEY")

#gateway de pagamento
MERCADOPAGO_ACCESS_TOKEN = _optional_env("MERCADOPAGO_ACCESS_TOKEN")
MERCADOPAGO_API_URL = _optional_env("MERCADOPAGO_API_URL", "https://api.mercadopago.com")
MERCADOPAGO_WEBHOOK_SECRET = _optional_env("MERCADOPAGO_WEBHOOK_SECRET")
MERCADOPAGO_CURRENCY_ID = _optional_env("MERCADOPAGO_CURRENCY_ID", "BRL")

#OAuth para logar
GOOGLE_CLIENT_ID: str     = _required_env("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET: str = _required_env("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI: str  = os.getenv(
    "GOOGLE_REDIRECT_URI",
    f"{BASE_URL}/auth/callback"
)

GOOGLE_AUTH_URL: str  = _optional_env("GOOGLE_AUTH_URL", "https://accounts.google.com/o/oauth2/v2/auth")
GOOGLE_TOKEN_URL:str = _optional_env("GOOGLE_TOKEN_URL", "https://oauth2.googleapis.com/token")
GOOGLE_USERINFO:str  = _optional_env("GOOGLE_USERINFO", "https://openidconnect.googleapis.com/v1/userinfo")
SCOPES: str           = _optional_env("SCOPES", "openid email profile")

APP_ENV = _optional_env("APP_ENV", "development")
APP_TIMEZONE = _optional_env("APP_TIMEZONE", "America/Sao_Paulo")
HOST = _optional_env("HOST", "0.0.0.0")
PORT = int(_optional_env("PORT", "8000"))
WORKER_POLL_SECONDS = float(_optional_env("WORKER_POLL_SECONDS", "15"))
SCRAPER_INTERVAL_SECONDS = float(_optional_env("SCRAPER_INTERVAL_SECONDS", "86400"))
TELEGRAM_SEND_DELAY_SECONDS = float(_optional_env("TELEGRAM_SEND_DELAY_SECONDS", "2"))
MAX_PRODUCTS_PER_RUN = int(_optional_env("MAX_PRODUCTS_PER_RUN", "50"))
DELIVERY_JOB_MAX_ATTEMPTS = int(_optional_env("DELIVERY_JOB_MAX_ATTEMPTS", "3"))
DELIVERY_JOB_RETRY_MINUTES = int(_optional_env("DELIVERY_JOB_RETRY_MINUTES", "10"))

#Mercado livre
ML_MIN_DISCOUNT: float = float(os.getenv("ML_MIN_DISCOUNT", "10"))   # % mínimo de desconto
ML_MAX_PER_CAT:  int   = int(os.getenv("ML_MAX_PER_CAT",   "100"))   # produtos por categoria
ML_BASE_URL: str = _optional_env("ML_BASE_URL", "https://lista.mercadolivre.com.br")

# Proxies para scrapers (lista separada por vírgula: http://user:pass@host:port,...)
_raw_proxies = _optional_env("ML_PROXY_URLS", "")
PROXY_URLS: list[str] = _parse_proxy_urls(_raw_proxies) or _load_proxy_urls()


#Lojas
SHOPIFY_URLS : dict[str, str] = {
    "Mad Enlatados": "https://madenlatados.com.br/products.json?limit=250",
    "New": "https://newnewnew.com.br/products.json?limit=250",
    "Piet": "https://piet.com.br/products.json?limit=250",
    "Pace": "https://pacecompany.com.br/products.json?limit=250",
    "Carnan": "https://www.carnan.com.br/products.json?limit=250",
    "1of1": "https://1of1exclusivist.com/products.json?limit=250",
    "EghoStudios": "https://egho.com.br/products.json?limit=250",
    "Sufgang": "https://sufgang.com.br/products.json?limit=250",
    "CienaLab": "https://cienalab.com.br/products.json?limit=250",
    "Anty": "https://www.anty.com.br/products.json?limit=250",
    "IceCompany": "https://www.icecompany.com.br/products.json"
}

NUVEMSHOP_URLS : dict[str, str] = {
    "Brunxind":"https://brunxind.com/",
    "Overstreets":"https://www.overstreets.com.br/",
    "Basyc":"https://www.basyc.com.br/",
    "Bussfly":"https://bussfly.com.br/",
    "Captive Club":"https://captiveclub.com.br/",
    "Malan":"https://www.malan.com.br/",
    "ggar":"https://ggar.com.br/",
    "Places Wo":"https://www.placeswo.com/",
    "Delafoe":"https://delafoe.com.br/",
    "SteetApparel":"https://www.streetapparel.com.br/",
    "Wanted":"https://wantedind.com/",
    "YungCeo":"https://yungceo.com.br/",
    "Jet Company": "https://jetcompanybr.com/",
    "Dest studios":"https://www.deststudios.com.br/",
    "TakeOff":"https://takeoffcollection.com.br/",
}

# category label → slug usado na URL de lista.mercadolivre.com.br
ML_CATEGORIES: dict[str, str] = {
    "ML-Monitor":        "monitor gamer",
    "ML-Notebook":       "notebook",
    "ML-PC-Gamer":       "pc gamer",
    "ML-SSD":            "ssd",
    "ML-Memória-RAM":    "memória ram",
    "ML-Placa-de-Video": "placa de vídeo",
    "ML-Processador":    "processador",
    "ML-Teclado":        "teclado gamer",
    "ML-Mouse":          "mouse gamer",
    "ML-Headset":        "headset gamer",
    "ML-Webcam":         "webcam",
    "ML-Smartphone":     "smartphone",
    "ML-Tablet":         "tablet",
    "ML-Smartwatch":     "smartwatch",
    "ML-Fone-Bluetooth": "fone bluetooth",
    "ML-Caixa-de-Som":   "caixa de som bluetooth",
    "ML-Camera-Digital": "câmera digital",
    "ML-Smart-TV":       "smart tv",
    "ML-Projetor":       "projetor",
}
