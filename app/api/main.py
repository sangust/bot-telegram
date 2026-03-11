from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.src.infrabackend.config import APP_ENV, SECRET_KEY
from app.src.infrabackend.database import check_db_connection

from .routes.auth import auth
from .routes.createbot import createbot
from .routes.dashboard import dashboard
from .routes.landingpage import landingpage as front_router
from .routes.subscription import subscription

app = FastAPI(title="afilibot")
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    https_only=APP_ENV == "production",
    same_site="lax",
)
app.include_router(front_router)
app.include_router(createbot)
app.include_router(dashboard)
app.include_router(auth)
app.include_router(subscription)

@app.get("/health")
async def healthcheck():
    db_ok = check_db_connection()
    status_code = 200 if db_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if db_ok else "degraded",
            "database": "ok" if db_ok else "error",
        },
    )