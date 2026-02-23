from fastapi import FastAPI
from .routes.landingpage import landingpage as front_router
from .routes.createbot import createbot
from .routes.dashboard import dashboard
from .routes.auth import auth
from .routes.subscription import subscription
from starlette.middleware.sessions import SessionMiddleware
import os

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "dev-secret-troque-em-producao"))
app.include_router(front_router)
app.include_router(createbot)
app.include_router(dashboard)
app.include_router(auth)
app.include_router(subscription)