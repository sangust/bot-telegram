from sqlalchemy import (
    Column, Integer, String, BigInteger, ForeignKey,
    Boolean, Numeric, UniqueConstraint, Enum, Index, DateTime, Text, Time)
from sqlalchemy.orm import relationship, declarative_base
import enum
from datetime import time
from datetime import datetime, timezone

BASE = declarative_base()


#precisa disso, se não python pega o momento de importacao do arquivo python -m src.infraback.models e não no momento do update
def _now():
    return datetime.now(timezone.utc)


#Classificar objetos para utilizar dentro dos schemas

class SubPlains(str, enum.Enum):
    free     = "free"
    freemium = "freemium"
    premium  = "premium"


class StatusSubPlains(str, enum.Enum):
    pending  = "pending"
    active   = "active"
    canceled = "canceled"
    expired  = "expired"


class PlanType(str, enum.Enum):
    monthly = "monthly"
    annual  = "annual"


class StatusBot(str, enum.Enum):
    active = "active"
    paused = "paused"


class DeliveryJobStatus(str, enum.Enum):
    pending   = "pending"
    running   = "running"
    succeeded = "succeeded"
    failed    = "failed"


class PaymentMethod(str, enum.Enum):
    pix  = "PIX"
    card = "CARD"


class Platform(str, enum.Enum):
    shopify   = "shopify"
    nuvemshop = "nuvemshop"
    mercadolivre = "mercadolivre"


class Store(BASE):
    """
    Catálogo de lojas disponíveis.
    A mesma loja (ex: Sufgang) pode estar em vários bots de vários usuários.
    Para adicionar uma nova loja basta inserir uma linha aqui, sem alterar código.
    """
    __tablename__ = "stores"

    brand         = Column(String, primary_key=True)
    url        = Column(String(500), nullable=False)
    platform   = Column(Enum(Platform), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    bot_stores = relationship("BotStore", back_populates="store")
    products   = relationship("Product",  back_populates="store")


# BotStore — tabela de junção Bot <-> Store 
# Relacionamento 1 bot -> várias lojas (e 1 loja -> vários bots).
class BotStore(BASE):
    __tablename__ = "bot_stores"

    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), primary_key=True)
    brand  = Column(String,  ForeignKey("stores.brand", ondelete="CASCADE"), primary_key=True)
    affiliate_link = Column(String(500), nullable=True)

    bot   = relationship("Bot",   back_populates="stores")
    store = relationship("Store", back_populates="bot_stores")


class Product(BASE):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("brand", "clothing_id", name="uq_clothing_per_store"),
        Index("ix_products_store_available_price", "brand", "available", "discount_price"),)

    id             = Column(Integer, primary_key=True)
    brand          = Column(String, ForeignKey("stores.brand"), nullable=False, index=True)
    name           = Column(String(200))
    size           = Column(String(100))
    discount_price = Column(Numeric(10, 2), nullable=False)
    full_price     = Column(Numeric(10, 2), nullable=False)
    image          = Column(String)
    available      = Column(Boolean, nullable=False)
    link           = Column(String)
    clothing_id    = Column(BigInteger, nullable=False)
    updated_at     = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    #loja que o produto pertence
    store = relationship("Store", back_populates="products")

class MLProduct(BASE):
    """
    Produtos raspados do Mercado Livre.
    Tabela própria — não usa a FK de stores nem o campo size,
    que não fazem sentido para o modelo do ML.
    """
    __tablename__ = "ml_products"
    __table_args__ = (
        UniqueConstraint("ml_item_id", name="uq_ml_item_id"),
        Index("ix_ml_products_category_discount", "category", "discount_pct"),
    )

    id             = Column(Integer,  primary_key=True)
    ml_item_id     = Column(String(20),  nullable=False, unique=True)  # ex: MLB1234567890
    category       = Column(String(50),  nullable=False, index=True)   # ex: ML-Celulares
    title          = Column(String(300), nullable=False)
    discount_price = Column(Numeric(10, 2), nullable=False)
    full_price     = Column(Numeric(10,  2), nullable=False)
    discount_pct   = Column(Numeric(5,  2), nullable=False)            # % pre-calculado
    image          = Column(String(500), nullable=True)
    link           = Column(Text, nullable=False)
    updated_at     = Column(DateTime(timezone=True), default=_now, onupdate=_now)




class User(BASE):
    __tablename__ = "users"

    google_id        = Column(String(100), primary_key=True, nullable=False)
    email            = Column(String(200), unique=True, nullable=False)
    name             = Column(String(200))
    subplain         = Column(Enum(SubPlains), default=SubPlains.free, nullable=False)
    trial_started_at = Column(DateTime(timezone=True), nullable=True, default=_now)
    created_at       = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at       = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    #Um user tem que ter os dados da subscription
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    #Um user tem que ter um bot
    bot          = relationship("Bot",          back_populates="user", uselist=False)



class Bot(BASE):
    __tablename__ = "bots"

    id              = Column(Integer, primary_key=True)
    user_id         = Column(String, ForeignKey("users.google_id"), unique=True, nullable=False, index=True)
    bot_token       = Column(String(300), nullable=False)
    chat_id         = Column(String(100), nullable=False)
    affiliate_link  = Column(String(300), nullable=True)
    today_sent      = Column(Integer, default=0, nullable=False)
    all_sent        = Column(Integer, default=0, nullable=False)
    last_reset_date = Column(DateTime(timezone=True), nullable=True)
    status          = Column(Enum(StatusBot), default=StatusBot.active, nullable=False)
    created_at      = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at      = Column(DateTime(timezone=True), default=_now, onupdate=_now)
    time_to_sent = Column(Time(timezone=True), nullable=False, default=time(12, 0))

    user       = relationship("User",     back_populates="bot")
    stores = relationship("BotStore", back_populates="bot", cascade="all, delete-orphan")
    schedules  = relationship("BotSchedule", back_populates="bot", cascade="all, delete-orphan")
    jobs       = relationship("DeliveryJob", back_populates="bot", cascade="all, delete-orphan")


class BotSchedule(BASE):
    __tablename__ = "bot_schedules"
    __table_args__ = (
        UniqueConstraint("bot_id", "run_time", name="uq_bot_schedule_time"),
    )

    id         = Column(Integer, primary_key=True)
    bot_id      = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    run_time    = Column(Time(timezone=True), nullable=False)
    created_at  = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at  = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    bot         = relationship("Bot", back_populates="schedules")
    jobs        = relationship("DeliveryJob", back_populates="schedule")


class DeliveryJob(BASE):
    __tablename__ = "delivery_jobs"
    __table_args__ = (
        Index("ix_delivery_jobs_status_run_at", "status", "run_at"),
        UniqueConstraint("bot_id", "schedule_id", "run_at", name="uq_delivery_job_schedule_run"),
    )

    id           = Column(Integer, primary_key=True)
    bot_id       = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    schedule_id  = Column(Integer, ForeignKey("bot_schedules.id", ondelete="SET NULL"), nullable=True, index=True)
    status       = Column(Enum(DeliveryJobStatus), default=DeliveryJobStatus.pending, nullable=False)
    run_at       = Column(DateTime(timezone=True), nullable=False, index=True)
    started_at   = Column(DateTime(timezone=True), nullable=True)
    finished_at  = Column(DateTime(timezone=True), nullable=True)
    attempts     = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    sent_count   = Column(Integer, default=0, nullable=False)
    last_error   = Column(Text, nullable=True)
    created_at   = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at   = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    bot         = relationship("Bot", back_populates="jobs")
    schedule    = relationship("BotSchedule", back_populates="jobs")


# ── Subscription ──────────────────────────────────────────────────────────────

class Subscription(BASE):
    __tablename__ = "subscriptions"

    id             = Column(Integer, primary_key=True)
    user_id        = Column(String, ForeignKey("users.google_id"), unique=True, nullable=False, index=True)
    billing_id     = Column(String(200), unique=True, nullable=False)
    customer_id    = Column(String(200), nullable=True)
    payment_method = Column(Enum(PaymentMethod), nullable=True)
    plan           = Column(Enum(PlanType), nullable=False)
    status         = Column(Enum(StatusSubPlains), default=StatusSubPlains.pending, nullable=False)
    amount         = Column(Integer, nullable=True)
    start          = Column(DateTime(timezone=True), nullable=True)
    next_payment   = Column(DateTime(timezone=True), nullable=True)
    canceled_at    = Column(DateTime(timezone=True), nullable=True)
    created_at     = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at     = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    user = relationship("User", back_populates="subscription")


#dados da cobranca confirmada
class Payment(BASE):
    """
    Histórico imutável de pagamentos.
    Subscription = estado atual. Payment = cada cobrança confirmada.
    """
    __tablename__ = "payments"

    id             = Column(Integer, primary_key=True)
    user_id        = Column(String, ForeignKey("users.google_id"), nullable=False, index=True)
    billing_id     = Column(String(200), nullable=False, index=True)
    amount         = Column(Integer, nullable=False)
    payment_method = Column(Enum(PaymentMethod), nullable=True)
    plan           = Column(Enum(PlanType), nullable=False)
    paid_at        = Column(DateTime(timezone=True), default=_now, nullable=False)

    user = relationship("User")


# 
class PendingChatId(BASE):
    """
    Armazena temporariamente o chat_id capturado pelo webhook do Telegram.
    Substitui o dict em memória — funciona com múltiplos workers.
    TTL de 10 minutos verificado na query.
    """
    __tablename__ = "pending_chat_ids"

    google_id  = Column(String, primary_key=True)
    bot_token  = Column(String(300), nullable=False)
    connection_code = Column(String(100), nullable=False, unique=True, index=True)
    chat_id    = Column(String(100), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    connected_at = Column(DateTime(timezone=True), nullable=True)