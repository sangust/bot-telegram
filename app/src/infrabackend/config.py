import os
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
ABACATEPAY_API_KEY = _optional_env("ABACATEPAY_API_KEY")
ABACATEPAY_API_URL = _optional_env("ABACATEPAY_API_URL", "https://api.abacatepay.com/v1")
ABACATEPAY_WEBHOOK_SECRET = _optional_env("ABACATEPAY_WEBHOOK_SECRET")

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
TELEGRAM_SEND_DELAY_SECONDS = float(_optional_env("TELEGRAM_SEND_DELAY_SECONDS", "2"))
MAX_PRODUCTS_PER_RUN = int(_optional_env("MAX_PRODUCTS_PER_RUN", "50"))
DELIVERY_JOB_MAX_ATTEMPTS = int(_optional_env("DELIVERY_JOB_MAX_ATTEMPTS", "3"))
DELIVERY_JOB_RETRY_MINUTES = int(_optional_env("DELIVERY_JOB_RETRY_MINUTES", "10"))

#Mercado livre auth
ML_MIN_DISCOUNT: float = float(os.getenv("ML_MIN_DISCOUNT", "10"))   # % mínimo de desconto
ML_MAX_PER_CAT:  int   = int(os.getenv("ML_MAX_PER_CAT",   "100"))   # produtos por categoria


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

ML_CATEGORIES: dict[str, str] = {
    "ML-Monitor":           "monitor-led",
    "ML-Notebook":          "notebook",
    "ML-PC-Gamer":          "pc-gamer",
    "ML-SSD":               "ssd",
    "ML-Memória-RAM":       "memoria-ram",
    "ML-Placa-de-Video":    "placa-de-video",
    "ML-Processador":       "processador",
    "ML-Fonte-PC":          "fonte-computador",
    "ML-Gabinete":          "gabinete-computador",

    "ML-Teclado":           "teclado-gamer",
    "ML-Mouse":             "mouse-gamer",
    "ML-Headset":           "headset-gamer",
    "ML-Webcam":            "webcam",
    "ML-Mousepad":          "mousepad-gamer",

    "ML-Smartphone":        "smartphone",
    "ML-Tablet":            "tablet",
    "ML-Smartwatch":        "smartwatch",

    "ML-Fone-Bluetooth":    "fone-ouvido-bluetooth",
    "ML-Caixa-de-Som":      "caixa-de-som-bluetooth",
    "ML-Camera-Digital":    "camera-digital",
    "ML-Camera-Seguranca":  "camera-seguranca",

    "ML-Smart-TV":          "smart-tv",
    "ML-Projetor":          "projetor",

    "ML-Roteador":          "roteador-wifi",
    "ML-Switch":            "switch-rede",
}

ML_BASE_URL     = "https://lista.mercadolivre.com.br"