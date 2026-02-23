from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from app.botrun import afilibot
from app.src.infrabackend.repository import LocalRepository
from app.src.infrabackend.database import LocalDatabase
from app.src.domain.models import Bot, StatusBot, User, SubPlains
from app.api.routes.auth import current_user
from fastapi.responses import RedirectResponse
import json
from datetime import date
from app.src.infrabackend.config import BOT_TOKENS

templates = Jinja2Templates("app/templates")
createbot = APIRouter(tags=["createbot"])

@createbot.get("/createbot")
async def create(request: Request):
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

    return templates.TemplateResponse("createbot.html", {"request": request})


@createbot.post("/api/setup-bot")
async def setup(request: Request, bg: BackgroundTasks):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login")
    data = await request.json()
    db = LocalDatabase()
    session = db.SESSION()
    bot_count = session.query(Bot).count()
    token = BOT_TOKENS[bot_count % len(BOT_TOKENS)]
    session.close()

    try:
        bot = Bot(
            user_id        = user["google_id"],
            bot_token      = token,
            chat_id        = data["chat_id"],
            stores         = json.dumps(data["stores"]),
            affiliate_link = data.get("affiliate_link"),
            today_sent     = 0,
            all_sent       = 0,
            status         = StatusBot.active,
            created_at     = date.today()
        )
        repo = LocalRepository()
        repo.add(bot)
        repo.commit()
    except Exception as e:
        return {"error": str(e)}

    bg.add_task(afilibot, data["chat_id"], data["stores"], token, data.get("affiliate_link"))
    return {"Bot criado com sucesso": 200}