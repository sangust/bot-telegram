import os
from dotenv import load_dotenv

#carrega as variavel de ambiente (.env)
load_dotenv()

#banco de dados
DATABASE_URL = os.getenv("DATABASE_URL")

#bot token telegram
BOT_TOKENS = [os.getenv("BOT_TOKEN_1"), os.getenv("BOT_TOKEN_2"), os.getenv("BOT_TOKEN_3")]

#url do site em prod ou dev
BASE_URL = os.getenv("BASE_URL")

#chave para cookie de sessao
SECRET_KEY = os.getenv("SECRET_KEY")

#gateway de pagamento
ABACATEPAY_API_KEY = os.getenv("ABACATEPAY_API_KEY")
ABACATEPAY_API_URL = os.getenv("ABACATEPAY_API_URL")
ABACATEPAY_WEBHOOK_SECRET = os.getenv("ABACATEPAY_WEBHOOK_SECRET")

#OAuth para logar
GOOGLE_CLIENT_ID: str     = os.environ["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET: str = os.environ["GOOGLE_CLIENT_SECRET"]
GOOGLE_REDIRECT_URI: str  = os.getenv(
    "GOOGLE_REDIRECT_URI",
    f"{BASE_URL}/auth/callback"
)

GOOGLE_AUTH_URL: str  = os.getenv("GOOGLE_AUTH_URL")
GOOGLE_TOKEN_URL:str = os.getenv("GOOGLE_TOKEN_URL")
GOOGLE_USERINFO:str  = os.getenv("GOOGLE_USERINFO")
SCOPES: str           = os.getenv("SCOPES")

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