import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
CONNECT_ARGS = {}

CREDENTIALS = os.getenv("CREDENTIALS")
PROJECT_ID = os.getenv("PROJECT_ID")
TABLE = os.getenv("TABLE")
BOT_TOKENS = [os.getenv("BOT_TOKEN_1"), os.getenv("BOT_TOKEN_2"), os.getenv("BOT_TOKEN_3")]
BASE_URL = "https://afilibot.shop" #prod
ABACATEPAY_API_KEY = os.getenv("ABACATEPAY_API_KEY")
ABACATEPAY_API_URL = os.getenv("ABACATEPAY_API_URL")
ABACATEPAY_WEBHOOK_SECRET = os.getenv("ABACATEPAY_WEBHOOK_SECRET")
SHOPIFY_URLS = {
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

NUVEMSHOP_URLS = {
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