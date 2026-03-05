from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.src.domain.models import Product, Bot, User, Subscription, Payment, Store, BotStore
from app.src.infrabackend.schemas import ProductSchema


class StoreRepository:
    """
    Chamadas de query na table de lojas.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> list[Store]:
        return self.db.query(Store).all()

    def get_by_platform(self, platform: str) -> list[Store]:
        return (
            self.db.query(Store)
            .filter(Store.platform == platform)
            .all()
        )

    def get_by_brand(self, brand: str) -> Store | None:
        return self.db.query(Store).filter(Store.brand == brand).first()

    def get_by_brands(self, brands: list[str]) -> list[Store]:
        return self.db.query(Store).filter(Store.brand.in_(brands)).all()


class BotRepository:
    """
    Chamadas de query na table de bots.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_by_user_id(self, user_id: str) -> Bot | None:
        return self.db.query(Bot).filter(Bot.user_id == user_id).first()

    def get_by_token(self, bot_token: str) -> Bot | None:
        return self.db.query(Bot).filter(Bot.bot_token == bot_token).first()

    def count(self) -> int:
        return self.db.query(Bot).count()

    def update(self, bot: Bot, **fields) -> Bot:
        for key, value in fields.items():
            if value is not None:
                setattr(bot, key, value)
        self.db.flush()
        return bot

    def set_stores(self, bot: Bot, stores: list[Store]) -> None:
        """
        Substitui todas as lojas do bot pelas novas.
        Deleta os BotStore existentes e recria com brand como FK.
        """
        self.db.query(BotStore).filter(BotStore.user_id_bot == bot.user_id).delete()
        for store in stores:
            self.db.add(BotStore(user_id_bot=bot.user_id, brand=store.brand))
        self.db.flush()

    def discount_products(self, brands: list[str], limit: int = 200) -> list:
        if not brands:
            return []

        return (
            self.db.query(
                Product.brand,
                Product.name,
                Product.discount_price,
                Product.full_price,
                Product.link,
                Product.image,
                func.string_agg(Product.size, ", ").label("size"),
            )
            .filter(
                Product.brand.in_(brands),
                Product.discount_price < Product.full_price,
                Product.available.is_(True),
            )
            .group_by(
                Product.brand,
                Product.name,
                Product.full_price,
                Product.link,
                Product.discount_price,
                Product.image,
            )
            .order_by(Product.full_price.asc())
            .limit(limit)
            .all()
        )
    
 

    def count_sents(self, brands: list[str], limit: int = 200) -> list:
        if not brands:
            return []

        return (
            self.db.query(Product)
            .filter(
                Product.brand.in_(brands),
                Product.discount_price < Product.full_price,
                Product.available.is_(True),
            ).limit(limit).count())

    def reset_today_sent_if_needed(self, bot: Bot) -> None:
        today      = datetime.now(timezone.utc).date()
        last_reset = bot.last_reset_date
        if last_reset is None or last_reset.date() < today:
            bot.today_sent      = 0
            bot.last_reset_date = datetime.now(timezone.utc)
            self.db.flush()


class ProductRepository:
    """
        Chamadas de query na table de produtos.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_by_brand_and_id(self, brand: str, clothing_id: int) -> Product | None:
        return (
            self.db.query(Product)
            .filter(Product.brand == brand, Product.clothing_id == clothing_id)
            .first()
        )

    def upsert(self, schema: ProductSchema, brand: str) -> None:
        existing = self.get_by_brand_and_id(brand, schema.clothing_id)
        if existing:
            existing.discount_price = schema.discount_price
            existing.full_price     = schema.full_price
            existing.available      = schema.available
            existing.updated_at     = datetime.now(timezone.utc)
        else:
            data    = schema.model_dump(exclude={"brand"})
            product = Product(**data, brand=brand)
            self.db.add(product)
        self.db.flush()


class UserRepository:
    """
        Chamadas de query na table de usuarios.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_by_google_id(self, google_id: str) -> User | None:
        return self.db.query(User).filter(User.google_id == google_id).first()

    def upsert(self, google_id: str, email: str, name: str) -> User:
        user = self.get_by_google_id(google_id)
        if not user:
            user = User(google_id=google_id, email=email, name=name)
            self.db.add(user)
        else:
            user.name = name
        self.db.flush()
        return user
    
    def get_subscription(self, google_id: str) -> User | None:
        return self.db.query(Subscription).filter(Subscription.user_id == google_id).first()


class SubscriptionRepository:
    """
        Chamadas de query na table de planos de pagamentos
    """
    def __init__(self, db: Session):
        self.db = db

    def get_by_user_id(self, user_id: str) -> Subscription | None:
        return (
            self.db.query(Subscription)
            .filter(Subscription.user_id == user_id)
            .first()
        )

    def get_by_billing_id(self, billing_id: str) -> Subscription | None:
        return (
            self.db.query(Subscription)
            .filter(Subscription.billing_id == billing_id)
            .first()
        )

    def create_or_update_pending(self, user_id: str, billing_id: str, plan: str, amount: int,) -> Subscription:
        """Criar uma tabela temporaria com os dados do checkout"""
        from app.src.domain.models import StatusSubPlains
        sub = self.get_by_user_id(user_id)
        if sub:
            sub.billing_id = billing_id
            sub.plan       = plan
            sub.status     = StatusSubPlains.pending
            sub.amount     = amount
        else:
            sub = Subscription(
                user_id    = user_id,
                billing_id = billing_id,
                plan       = plan,
                status     = StatusSubPlains.pending,
                amount     = amount,
            )
            self.db.add(sub)
        self.db.flush()
        return sub

    def record_payment(self, sub: Subscription) -> None:
        payment = Payment(
            user_id        = sub.user_id,
            billing_id     = sub.billing_id,
            amount         = sub.amount,
            payment_method = sub.payment_method,
            plan           = sub.plan,
        )
        self.db.add(payment)
        self.db.flush()