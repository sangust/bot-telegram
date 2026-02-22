from sqlalchemy import (
    Column, Integer, String, BigInteger, ForeignKey,
    Boolean, Date, Numeric, UniqueConstraint, Enum)
from sqlalchemy.orm import relationship
import enum
from datetime import date
from sqlalchemy.orm import declarative_base

BASE = declarative_base()

class SubPlains(str, enum.Enum):
    free  = "free"    # sem bot, só visualiza
    basic = "basic"   # 1 bot, 1 chat


class StatusSubPlains(str, enum.Enum):
    active    = "active"
    canceled = "canceled"
    expired  = "expired"
    pending  = "pending"   # aguardando pagamento


class StatusBot(str, enum.Enum):
    active   = "active"
    paused = "paused"


class Product(BASE):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("brand", "clothing_id", name="unique_id_clothing_per_brand"),)

    id = Column(Integer, primary_key=True)
    brand = Column(String(100), nullable=False)
    name = Column(String(200))
    size = Column(String(50))
    discount_price = Column(Numeric(10, 2), nullable=False)
    full_price = Column(Numeric(10,2), nullable=False)
    image = Column(String)
    available = Column(Boolean, nullable=False)
    link = Column(String)
    clothing_id = Column(BigInteger, nullable=False)
    sent_at = Column(Date)

class User(BASE):
    __tablename__ = "users"

    google_id  = Column(String(100), primary_key=True, unique=True, nullable=False)  # sub do token Google
    email      = Column(String(200), unique=True, nullable=False)
    name       = Column(String(200))
    subplain      = Column(Enum(SubPlains), default=SubPlains.free, nullable=False)
    created_at  = Column(Date, default=Date)

    subscription = relationship("Subscription", back_populates="user", uselist=False)
    bot = relationship("Bot", back_populates="user", uselist=False)

class Bot(BASE):
    __tablename__ = "bots"

    id              = Column(Integer, primary_key=True)
    user_id         = Column(String, ForeignKey("users.google_id"), unique=True, nullable=False)  
    bot_token       = Column(String(300), nullable=False)
    chat_id         = Column(String(100), nullable=False) 
    stores           = Column(String)  
    affiliate_link   = Column(String(300), nullable=True)
    sent_time   = Column(Integer, default=9) 
    status          = Column(Enum(StatusBot), default=StatusBot.active)
    created_at       = Column(Date)
    updated_at   = Column(Date, default=Date, onupdate=date.today)

    user = relationship("User", back_populates="bot")



class Subscription(BASE):
    __tablename__ = "subscriptions"

    id                   = Column(Integer, primary_key=True)
    user_id              = Column(String, ForeignKey("users.google_id"), unique=True, nullable=False)
    abacatepay_id        = Column(String(200), unique=True)         # ID da cobrança/assinatura lá
    abacatepay_customer  = Column(String(200))                      # customer ID no Abacatepay

    status               = Column(Enum(StatusSubPlains), default=StatusSubPlains.pending)
    value                = Column(Numeric(10, 2))                   
    start               = Column(Date)
    next_payment   = Column(Date)
    canceled_at         = Column(Date, nullable=True)

    created_at            = Column(Date, default=date.today)
    updated_at        = Column(Date, default=date.today, onupdate=date.today)

    user = relationship("User", back_populates="subscription")
