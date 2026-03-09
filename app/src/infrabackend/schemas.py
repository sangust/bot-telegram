from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator
from datetime import datetime, time
from typing import Optional
from app.src.domain.models import (SubPlains, StatusSubPlains, StatusBot, PlanType, PaymentMethod, Platform)



class StoreSchema(BaseModel):
    brand: str
    url:        str
    platform:   Platform

    model_config = {"from_attributes": True}



class ProductSchema(BaseModel):
    brand:          str
    name:           str
    size:           str
    full_price:     float = Field(gt=0)
    discount_price: float = Field(gt=0)
    available:      bool
    image:          Optional[str]      = None
    link:           str
    clothing_id:    int

    @model_validator(mode="after")
    def discount_must_be_lte_full(self) -> "ProductSchema":
        if self.discount_price > self.full_price:
            raise ValueError(
                f"discount_price ({self.discount_price}) não pode ser maior "
                f"que full_price ({self.full_price})"
            )
        return self



class UserSchema(BaseModel):
    google_id:  str
    email:      EmailStr
    name:       Optional[str]      = None
    subplain:   SubPlains          = SubPlains.freemium
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}



class BotCreateSchema(BaseModel):
    """
    Usado ao criar/atualizar um bot via POST /api/setup-bot.
    store_ids é uma lista de IDs de Store — resolvidos a partir
    do que o usuário selecionou no frontend.
    """
    user_id:        str
    bot_token:      str
    chat_id:        str
    store_brands:   list[str]          
    affiliate_link: Optional[str]      = None
    status:         StatusBot          = StatusBot.active

    @field_validator("store_brands")
    @classmethod
    def must_have_at_least_one_store(cls, brand: list[str]) -> list[str]:
        if not brand:
            raise ValueError("O bot precisa ter ao menos uma loja selecionada.")
        return brand


class BotSchema(BaseModel):
    """Schema de leitura do bot (resposta da API)."""
    user_id:        str
    bot_token:      str
    chat_id:        str
    stores:         list[StoreSchema]  = []   # lojas como objetos, não JSON string
    affiliate_link: Optional[str]      = None
    today_sent:     int                = 0
    all_sent:       int                = 0
    status:         Optional[StatusBot] = None
    created_at:     Optional[datetime] = None
    updated_at:     Optional[datetime] = None
    time_to_sent: Optional[time] = time(12,0)

    model_config = {"from_attributes": True}



class SubscriptionSchema(BaseModel):
    user_id:         str
    billing_id:      str
    customer_id:     Optional[str]           = None
    payment_method:  Optional[PaymentMethod] = None
    plan:            PlanType = SubPlains.premium
    status:          StatusSubPlains
    amount:          Optional[int]           = None
    start:           Optional[datetime]      = None
    next_payment:    Optional[datetime]      = None
    canceled_at:     Optional[datetime]      = None
    created_at:      Optional[datetime]      = None
    updated_at:      Optional[datetime]      = None

    model_config = {"from_attributes": True}



class CheckoutRequestSchema(BaseModel):
    plan: PlanType

    model_config = {"use_enum_values": True}