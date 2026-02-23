from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.api.routes.auth import current_user
from app.src.infrabackend.repository import LocalRepository
from app.src.infrabackend.database import LocalDatabase
from app.src.domain.models import Bot, Product, User, SubPlains
from datetime import date
import json

templates = Jinja2Templates("app/templates")
dashboard = APIRouter(tags=["dashboard"])


@dashboard.get("/dashboard")
async def dashboardpage(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login")

    db = LocalDatabase()
    session = db.SESSION()
    try:
        user_obj = session.query(User).filter(User.google_id == user["google_id"]).first()
        if not user_obj or user_obj.subplain == SubPlains.free:
            return RedirectResponse("/subscription")
    finally:
        session.close()

    return templates.TemplateResponse("dashboard.html", {"request": request})


@dashboard.get("/api/dashboard/me")
async def me(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    return {"name": user["name"], "email": user["email"]}


@dashboard.get("/api/dashboard/stats")
async def stats(request: Request):
    """Apenas lê os contadores — nunca escreve."""
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    db = LocalRepository()
    try:
        bot = db.session.query(Bot).filter(Bot.user_id == user["google_id"]).first()
        if not bot:
            return {"has_bot": False, "stores": [], "sent_today": 0, "sent_total": 0}

        stores = list(json.loads(bot.stores).keys()) if bot.stores else []

        return {
            "has_bot":    True,
            "stores":     stores,
            "sent_today": bot.today_sent or 0,
            "sent_total": bot.all_sent or 0,
        }
    finally:
        db.session.close()



@dashboard.get("/api/dashboard/logs")
async def bot_logs(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    db = LocalRepository()
    try:
        bot = db.session.query(Bot).filter(Bot.user_id == user["google_id"]).first()
        if not bot or not bot.stores:
            return {"logs": []}

        stores = list(json.loads(bot.stores).keys())

        products = db.session.query(Product)\
    .filter(
        Product.brand.in_(stores),
        Product.discount_price < Product.full_price,
        Product.available.is_(True)
    )\
    .distinct(Product.name)\
    .order_by(Product.name, Product.id.desc())\
    .limit(10)\
    .all()

        return {"logs": [
            {
                "name":           p.name,
                "brand":          p.brand,
                "discount_price": float(p.discount_price),
                "full_price":     float(p.full_price),
                "sent_at":        str(p.sent_at) if p.sent_at else None,
            }
            for p in products
        ]}
    finally:
        db.session.close()