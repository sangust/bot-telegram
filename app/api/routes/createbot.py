import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.routes.auth import current_user
from app.src.domain.models import Bot, PendingChatId, PlanType, Platform, StatusBot, Store, SubPlains
from app.src.infrabackend.database import get_db
from app.src.infrabackend.config import ML_BASE_URL, ML_CATEGORIES
from app.src.infrabackend.repository import BotRepository, PendingChatRepository, StoreRepository, UserRepository
from app.src.services.delivery import (
    bot_token_for_alias,
    connect_chat_by_code,
    enqueue_immediate_delivery,
    ensure_telegram_webhook,
    fetch_bot_username,
    get_pending_connection,
    parse_schedule_times,
    reserve_telegram_connection,
    select_bot_token,
    sync_bot_schedules,
)

logger    = logging.getLogger(__name__)
templates = Jinja2Templates("app/templates")
createbot = APIRouter(tags=["createbot"])


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

    existing_bot = BotRepository(db).get_by_user_id(google_id)
    bot_token = existing_bot.bot_token if existing_bot else select_bot_token(google_id)
    bot_username = await fetch_bot_username(bot_token) or "afilibot"

    return templates.TemplateResponse(
        "createbot.html",
        {
            "request": request,
            "bot_username": bot_username,
        },
    )


@createbot.get("/api/telegram/add-to-group")
async def add_to_group(request: Request, db: Session = Depends(get_db)):
    google_id = request.session.get("google_id")
    if not google_id:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    existing_bot = BotRepository(db).get_by_user_id(google_id)
    bot_token = existing_bot.bot_token if existing_bot else select_bot_token(google_id)
    bot_username = await fetch_bot_username(bot_token)
    if not bot_username:
        return JSONResponse({"error": "Não foi possível obter username do bot"}, status_code=500)

    try:
        await ensure_telegram_webhook(bot_token)
        pending = reserve_telegram_connection(db, google_id, bot_token)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Erro ao preparar conexão do Telegram para user %s", google_id)
        return JSONResponse({"error": "Não foi possível preparar a conexão do Telegram"}, status_code=500)

    return RedirectResponse(f"https://t.me/{bot_username}?startgroup=afili_{pending.connection_code}")


@createbot.post("/api/telegram/webhook/{bot_alias}")
async def telegram_webhook(bot_alias: str, request: Request, db: Session = Depends(get_db)):
    bot_token = bot_token_for_alias(bot_alias)
    if not bot_token:
        raise HTTPException(status_code=404, detail="Bot não encontrado")

    try:
        body = await request.json()
    except Exception:
        return {"ok": True}

    now = datetime.now(timezone.utc)

    message = body.get("message") or body.get("edited_message")
    if message:
        text = (message.get("text") or message.get("caption") or "").strip()
        chat = message.get("chat", {})
        chat_id = str(chat.get("id")) if chat.get("id") is not None else None
        if text and chat_id:
            pendings = (
                db.query(PendingChatId)
                .filter(
                    PendingChatId.bot_token == bot_token,
                    PendingChatId.expires_at > now,
                )
                .all()
            )
            for pending in pendings:
                if pending.connection_code in text:
                    connect_chat_by_code(db, pending.connection_code, bot_token, chat_id)
                    db.commit()
                    return {"ok": True}

    if "my_chat_member" in body:
        new_status = body["my_chat_member"].get("new_chat_member", {}).get("status")
        if new_status in ("member", "administrator"):
            chat_id = str(body["my_chat_member"]["chat"].get("id"))
            pendings = (
                db.query(PendingChatId)
                .filter(
                    PendingChatId.bot_token == bot_token,
                    PendingChatId.expires_at > now,
                    PendingChatId.chat_id.is_(None),
                )
                .all()
            )
            if len(pendings) == 1:
                pendings[0].chat_id = chat_id
                pendings[0].connected_at = now
                db.commit()

    return {"ok": True}


@createbot.get("/api/telegram/chat-id")
async def get_pending_chat_id(request: Request, db: Session = Depends(get_db)):
    google_id = request.session.get("google_id")
    if not google_id:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    pending = get_pending_connection(db, google_id)
    if pending and pending.chat_id:
        return {"chat_id": pending.chat_id, "found": True}
    return {"found": False}


@createbot.post("/api/setup-bot")
async def setup(request: Request, db: Session = Depends(get_db)):
    google_id = request.session.get("google_id")
    if not google_id:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    user = current_user(request, db)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    data = await request.json()
    selected_brands = data.get("brands", [])
    affiliate_links = data.get("affiliate_links") or {}
    default_affiliate_link = data.get("affiliate_link") or None
    schedule_values = data.get("schedule_times") or []
    requested_chat_id = data.get("chat_id")

    if not selected_brands:
        return JSONResponse({"error": "Selecione ao menos uma loja."}, status_code=400)

    max_stores = 3 if user["subscription_plan"] != PlanType.annual else 99
    ml_selected = any(brand.startswith("ML-") for brand in selected_brands)
    regular_selected = [brand for brand in selected_brands if not brand.startswith("ML-")]
    selected_sources = len(regular_selected) + (1 if ml_selected else 0)
    if selected_sources > max_stores:
        return JSONResponse(
            {"error": f"Seu plano permite no máximo {max_stores} lojas."},
            status_code=400,
        )

    pending = get_pending_connection(db, google_id)
    chat_id = pending.chat_id if pending and pending.chat_id else requested_chat_id
    if not chat_id:
        return JSONResponse({"error": "Conecte o bot ao grupo antes de continuar."}, status_code=400)

    stores = StoreRepository(db).get_by_brands(selected_brands)
    existing_by_brand = {store.brand: store for store in stores}
    for brand in selected_brands:
        if brand in existing_by_brand:
            continue
        if brand in ML_CATEGORIES:
            store = Store(brand=brand, url=ML_BASE_URL, platform=Platform.mercadolivre)
            db.add(store)
            db.flush()
            stores.append(store)
            existing_by_brand[brand] = store

    if not stores:
        return JSONResponse({"error": "Nenhuma loja válida encontrada."}, status_code=400)

    allow_multiple = user["subscription_plan"] == PlanType.annual
    schedule_times = parse_schedule_times(schedule_values, allow_multiple=allow_multiple)

    bot_repo = BotRepository(db)
    bot = bot_repo.get_by_user_id(google_id)
    is_new_bot = bot is None
    bot_token = bot.bot_token if bot else (pending.bot_token if pending else select_bot_token(google_id))

    if bot:
        bot_repo.update(
            bot,
            bot_token=bot_token,
            chat_id=chat_id,
            affiliate_link=default_affiliate_link,
            status=StatusBot.active,
            time_to_sent=schedule_times[0],
        )
    else:
        bot = Bot(
            user_id=google_id,
            bot_token=bot_token,
            chat_id=chat_id,
            affiliate_link=default_affiliate_link,
            time_to_sent=schedule_times[0],
            today_sent=0,
            all_sent=0,
            status=StatusBot.active,
        )
        db.add(bot)
        db.flush()

    bot_repo.set_stores(bot, stores, affiliate_links=affiliate_links)
    sync_bot_schedules(db, bot, schedule_times)
    if is_new_bot:
        enqueue_immediate_delivery(db, bot)
    PendingChatRepository(db).delete_by_google_id(google_id)

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Erro ao salvar bot para user %s", google_id)
        return JSONResponse({"error": "Erro ao salvar bot"}, status_code=500)

    return {"ok": True}