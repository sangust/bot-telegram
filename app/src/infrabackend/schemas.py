from pydantic import BaseModel, Field, EmailStr
from datetime import date
from typing import Optional

class ProductSchema(BaseModel):
    brand: str
    name: str
    size: str
    full_price:  Optional[float] 
    discount_price: float = Field(gt=0)
    available: bool
    image: Optional[str]
    link: str
    clothing_id: int
    sent_at: Optional[date]

class UserSchema(BaseModel):
    google_id: str
    email: EmailStr
    name: Optional[str]
    subplain: str
    created_at: Optional[date]


class BotSchema(BaseModel):
    user_id: str
    bot_token: str
    chat_id: str
    stores: Optional[str]
    affiliate_link: Optional[str]
    today_sent: int
    all_sent: int
    status: Optional[str]
    created_at: Optional[date]
    updated_at: Optional[date]

class SubscriptionSchema(BaseModel):
    user_id: int
    abacatepay_id: Optional[str]
    abacatepay_customer: Optional[str]
    status: Optional[str]
    value: Optional[float]
    start: Optional[date]
    next_payment: Optional[date]
    canceled_at: Optional[date]
    created_at: Optional[date]
    updated_at: Optional[date]