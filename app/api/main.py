from fastapi import FastAPI
from .routes.landingpage import landingpage as front_router
from .routes.createbot import createbot
from .routes.dashboard import dashboard

app = FastAPI()
app.include_router(front_router)
app.include_router(createbot)
app.include_router(dashboard)