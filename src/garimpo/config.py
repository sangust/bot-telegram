from telegram import Bot
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///data/products.db"
ENGINE = create_engine(DATABASE_URL, echo=False)
SESSION = sessionmaker(bind=ENGINE)
BASE = declarative_base()

BOT_TOKEN = "8427864539:AAGHJ4mGbgu67ulxmXJo3-WvHgldj2jGc_s"
CHAT_ID = "-1003531860533"
BOT = Bot(token=BOT_TOKEN)


SHOP_URLS = {
    "Mad Enlatados": "https://madenlatados.com.br/products.json?limit=250",
    "New New New": "https://newnewnew.com.br/products.json?limit=250",
    "PIET": "https://piet.com.br/products.json?limit=250",
    "Pace": "https://pacecompany.com.br/products.json?limit=250",
    "Carnan": "https://www.carnan.com.br/products.json?limit=250",
    "1of1": "https://1of1exclusivist.com/products.json?limit=250",
    "egho studios": "https://egho.com.br/products.json?limit=250",
    "sufgang": "https://sufgang.com.br/products.json?limit=250",
    "ciena lab": "https://cienalab.com.br/products.json?limit=250",
    "anty": "https://www.anty.com.br/products.json?limit=250"
}

def criar_table():
    BASE.metadata.create_all(bind=ENGINE)
