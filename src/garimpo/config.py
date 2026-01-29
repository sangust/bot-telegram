from telegram import Bot
from telegram.request import HTTPXRequest
from dotenv import load_dotenv
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///data/products.db"
ENGINE = create_engine(DATABASE_URL, echo=False)
SESSION = sessionmaker(bind=ENGINE)
BASE = declarative_base()

request = HTTPXRequest(
    connect_timeout=30,
    read_timeout=30,
    write_timeout=30,
    pool_timeout=30
)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BOT = Bot(token=BOT_TOKEN, request=request)


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
    "anty": "https://www.anty.com.br/products.json?limit=250",
    "icecompany": "https://www.icecompany.com.br/products.json"
}

def criar_table():
    BASE.metadata.create_all(bind=ENGINE)
load_dotenv()