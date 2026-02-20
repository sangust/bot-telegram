from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.main import afilibot

templates = Jinja2Templates("app/templates")
createbot = APIRouter(tags=["createbot"])

@createbot.get("/createbot")
async def create(request: Request):
    return templates.TemplateResponse("createbot.html", {"request":request})

@createbot.post("/api/setup-bot")
async def setup(request:Request, bg: BackgroundTasks):
    data:dict = await request.json()
    bg.add_task(
        afilibot,
        data["chat_id"],
        data["stores"],
        data["affiliate_link"]
    )

    return {"success":200}