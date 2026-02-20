from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles


templates = Jinja2Templates("app/templates")
landingpage = APIRouter(tags=["landingpage"])

@landingpage.get("/")
async def home(request: Request):
    return templates.TemplateResponse("landingpage.html", {"request":request})
