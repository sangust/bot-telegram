from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles


templates = Jinja2Templates("app/templates")
dashboard = APIRouter(tags=["dashboard"])

@dashboard.get("/dashboard")
async def dashboardpage(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request":request})

@dashboard.post("/api/setup-bot")
async def setup(request:Request):
    data = await request.json()
    return {"sucess": data}