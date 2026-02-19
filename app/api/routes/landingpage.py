from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates("app/templates")
landingpage = APIRouter(tags=["landingpage"])

@landingpage.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request":request})