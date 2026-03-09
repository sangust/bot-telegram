import logging
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import APIRouter, Request, BackgroundTasks, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.src.infrabackend.database import get_db
from app.src.infrabackend.repository import BotRepository, StoreRepository, UserRepository
from app.src.domain.models import Bot, User, SubPlains, StatusBot, BotStore, PendingChatId, PlanType
from app.src.infrabackend.config import BOT_TOKENS, BASE_URL
from app.botrun import afilibot
from app.api.routes.auth import current_user

logger    = logging.getLogger(__name__)
templates = Jinja2Templates("app/templates")
createbot = APIRouter(tags=["createbot"])


def get_next_token(db: Session) -> str:
    bot_count = BotRepository(db).count()
    return BOT_TOKENS[bot_count % len(BOT_TOKENS)]


async def fetch_bot_username(token: str) -> str | None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.telegram.org/bot{token}/getMe",
                timeout=5,
            )
            if resp.status_code == 200:
                return resp.json().get("result", {}).get("username")
    except Exception:
        logger.warning("Não foi possível obter username do token %s...", token[:10])
    return None



@createbot.get("/api/stores")
async def list_stores(db: Session = Depends(get_db)):
    stores = StoreRepository(db).get_all()
    return [{"brand": s.brand, "platform": s.platform} for s in stores]



@createbot.get("/createbot")
async def create(request: Request, db: Session = Depends(get_db)):
    google_id = request.session.get("google_id")
    if not google_id:
        return RedirectResponse("/login")

    user = UserRepository(db).get_by_google_id(google_id)
    if not user:
        return RedirectResponse("/login")

    if user.subplain == SubPlains.free:
        return RedirectResponse("/subscription")

    if request.query_params.get("payment") == "success":
        return templates.TemplateResponse("createbot.html", {
            "request": request, "bot_username": "",
        })

    token        = get_next_token(db)
    bot_username = await fetch_bot_username(token) or "afilibot"

    return templates.TemplateResponse("createbot.html", {
        "request": request, "bot_username": bot_username,
    })




@createbot.get("/api/telegram/add-to-group")
async def add_to_group(request: Request, db: Session = Depends(get_db)):
    google_id = request.session.get("google_id")
    if not google_id:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    token        = get_next_token(db)
    bot_username = await fetch_bot_username(token)
    if not bot_username:
        return JSONResponse({"error": "Não foi possível obter username do bot"}, status_code=500)

    webhook_url = f"{BASE_URL}/api/telegram/webhook/{google_id}"
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={"url": webhook_url, "allowed_updates": ["my_chat_member"]},
            timeout=10,
        )

    return RedirectResponse(f"https://t.me/{bot_username}?startgroup=1")


@createbot.post("/api/telegram/webhook/{google_id}")
async def telegram_webhook(google_id: str, request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
    except Exception:
        return {"ok": True}

    if "my_chat_member" in body:
        new_status = body["my_chat_member"].get("new_chat_member", {}).get("status")
        if new_status in ("member", "administrator"):
            chat_id    = str(body["my_chat_member"]["chat"]["id"])
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

            existing = db.query(PendingChatId).filter(
                PendingChatId.google_id == google_id
            ).first()

            if existing:
                existing.chat_id    = chat_id
                existing.expires_at = expires_at
            else:
                db.add(PendingChatId(
                    google_id  = google_id,
                    chat_id    = chat_id,
                    expires_at = expires_at,
                ))
            db.commit()

    return {"ok": True}




@createbot.get("/api/telegram/chat-id")
async def get_pending_chat_id(request: Request, db: Session = Depends(get_db)):
    google_id = request.session.get("google_id")
    if not google_id:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    now     = datetime.now(timezone.utc)
    pending = db.query(PendingChatId).filter(
        PendingChatId.google_id  == google_id,
        PendingChatId.expires_at >  now,
    ).first()

    if pending:
        return {"chat_id": pending.chat_id, "found": True}
    return {"found": False}



@createbot.post("/api/setup-bot")
async def setup(request: Request, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Body esperado:
    {
        "chat_id":        "-100123456789",
        "brands":         ["Sufgang", "Piet", "New"],
        "affiliate_link": "ref=meuafiliado"   (opcional)
    }
    """
    google_id = request.session.get("google_id")
    if not google_id:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    data           = await request.json()
    brands         = data.get("brands", [])
    ml_categories  = data.get("ml_categories", [])
    affiliate_link = data.get("affiliate_link") or None
    chat_id        = data.get("chat_id")
    schedule_times   = data.get("schedule_times") or None    


    all_brands = brands + ml_categories

    if not all_brands:
        return JSONResponse({"error": "Selecione ao menos uma loja."}, status_code=400)
    if not chat_id:
        return JSONResponse({"error": "chat_id ausente."}, status_code=400)

    user = current_user(request, db)
    max_stores = 3 if user["subscription_plan"] != PlanType.annual else 99
    if len(all_brands) > max_stores:
        return JSONResponse(
            {"error": f"Seu plano permite no máximo {max_stores} lojas."},
            status_code=400,
        )

    store_repo = StoreRepository(db)
    stores     = store_repo.get_by_brands(all_brands)
    if not stores:
        return JSONResponse({"error": "Nenhuma loja válida encontrada."}, status_code=400)

    db.query(PendingChatId).filter(PendingChatId.google_id == google_id).delete()

    token    = get_next_token(db)
    bot_repo = BotRepository(db)
    bot      = bot_repo.get_by_user_id(google_id)

    if bot:
        bot_repo.update(bot,
            bot_token        = token,
            chat_id          = chat_id,
            affiliate_link   = affiliate_link,
            time_to_sent   = schedule_times,
        )
        bot_repo.set_stores(bot, stores)
    else:
        bot = Bot(
            user_id          = google_id,
            bot_token        = token,
            chat_id          = chat_id,
            affiliate_link   = affiliate_link,
            time_to_sent   = schedule_times,
            today_sent       = 0,
            all_sent         = 0,
            status           = StatusBot.active
        )
        db.add(bot)
        db.flush() 
        bot_repo.set_stores(bot, stores)

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Erro ao salvar bot para user %s", google_id)
        return JSONResponse({"error": "Erro ao salvar bot"}, status_code=500)

    bg.add_task(afilibot, chat_id, all_brands, token, affiliate_link)
    return {"ok": True}