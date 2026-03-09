import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.src.infrabackend.database import get_db
from app.src.infrabackend.repository import BotRepository, DeliveryJobRepository
from app.src.domain.models import Bot, Product, SubPlains, PlanType
from app.api.routes.auth import current_user

logger    = logging.getLogger(__name__)
templates = Jinja2Templates("app/templates")
dashboard = APIRouter(tags=["dashboard"])


@dashboard.get("/dashboard")
async def dashboard_page(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login")
    if user["plan"] == SubPlains.free:
        return RedirectResponse("/subscription")
    return templates.TemplateResponse("dashboard.html", {"request": request})


@dashboard.get("/api/dashboard/me")
async def me(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    return {
        "name":              user["name"],
        "email":             user["email"],
        "subscription_plan": user["subscription_plan"],
    }


# Limites por plano
PLAN_LIMITS = {
    PlanType.monthly: {"max_stores": 3,  "max_daily": 50,  "max_bots": 1, "custom_templates": False},
    PlanType.annual:  {"max_stores": 99, "max_daily": 200, "max_bots": 2, "custom_templates": True},
}


@dashboard.get("/api/dashboard/stats")
async def stats(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    limits = PLAN_LIMITS.get(user["subscription_plan"], PLAN_LIMITS[PlanType.monthly])

    repo = BotRepository(db)
    bot  = repo.get_by_user_id(user["google_id"])

    if not bot:
        return {
            "has_bot":    False,
            "stores":     [],
            "sent_today": 0,
            "sent_total": 0,
            "subscription_plan": user["subscription_plan"],
            "limits": limits,
        }

    stores = [{"brand": bs.brand} for bs in bot.stores]
    jobs_repo = DeliveryJobRepository(db)

    repo.reset_today_sent_if_needed(bot)
    db.commit()

    return {
        "has_bot":    True,
        "stores":     stores,
        "sent_today": bot.today_sent or 0,
        "sent_total": bot.all_sent   or 0,
        "status":     bot.status,
        "pending_jobs": jobs_repo.count_pending(bot.id),
        "recent_jobs": [job.status for job in jobs_repo.get_latest_for_bot(bot.id, limit=3)],
        "subscription_plan": user["subscription_plan"],
        "limits": limits,
    }


@dashboard.get("/api/dashboard/logs")
async def bot_logs(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    bot = db.query(Bot).filter(Bot.user_id == user["google_id"]).first()
    if not bot or not bot.stores:
        return {"logs": []}

    brands = [bs.brand for bs in bot.stores]

    subq = (
        db.query(Product.name, func.max(Product.id).label("max_id"))
        .filter(
            Product.brand.in_(brands),
            Product.discount_price < Product.full_price,
            Product.available.is_(True),
        )
        .group_by(Product.name)
        .subquery()
    )

    products = (
        db.query(Product)
        .join(subq, Product.id == subq.c.max_id)
        .order_by(Product.name)
        .limit(10)
        .all()
    )

    return {
        "logs": [
            {
                "name":           p.name,
                "brand":          p.store.brand,
                "discount_price": float(p.discount_price),
                "full_price":     float(p.full_price),
            }
            for p in products
        ]
    }