import logging
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.src.infrabackend.database import get_db
from app.src.infrabackend.repository import UserRepository, SubscriptionRepository
from app.src.domain.models import StatusSubPlains
from app.src.infrabackend.config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    GOOGLE_AUTH_URL,
    GOOGLE_TOKEN_URL,
    GOOGLE_USERINFO,
    SCOPES,
)

logger = logging.getLogger(__name__)

auth      = APIRouter(tags=["auth"])
templates = Jinja2Templates("app/templates")



# ── Login ─────────────────────────────────────────────────────────────────────

@auth.get("/login")
async def login_page(request: Request):
    if request.session.get("google_id"):
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse("login.html", {"request": request})



@auth.get("/auth/login")
async def login_redirect():
    params = urlencode({
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         SCOPES,
        "access_type":   "offline",
        "prompt":        "select_account",
    })
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{params}")


# ── Callback do Google ────────────────────────────────────────────────────────

@auth.get("/auth/callback")
async def callback(
    request: Request,
    code:    str,
    db:      Session = Depends(get_db),   # sessão gerenciada pelo FastAPI
):
    # 1. Troca o code por access_token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code":          code,
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri":  GOOGLE_REDIRECT_URI,
                "grant_type":    "authorization_code",
            },
        )

    if token_resp.status_code != 200:
        logger.error("Falha ao obter token Google: %s", token_resp.text)
        raise HTTPException(status_code=400, detail="Falha ao obter token do Google.")

    access_token = token_resp.json().get("access_token")

    # 2. Busca dados do usuário
    async with httpx.AsyncClient() as client:
        userinfo_resp = await client.get(
            GOOGLE_USERINFO,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if userinfo_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Falha ao buscar dados do usuário.")

    userinfo  = userinfo_resp.json()
    google_id = userinfo.get("sub")
    email     = userinfo.get("email")
    name      = userinfo.get("name", "")

    if not google_id or not email:
        raise HTTPException(status_code=400, detail="Dados insuficientes retornados pelo Google.")

    # 3. Upsert no banco — sessão fechada automaticamente pelo Depends ao final
    repo = UserRepository(db)
    try:
        repo.upsert(google_id=google_id, email=email, name=name)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("Erro ao salvar usuário %s", google_id)
        raise HTTPException(status_code=500, detail="Erro ao salvar usuário.")

    # 4. Salva na sessão
    request.session["google_id"] = google_id
    request.session["email"]     = email
    request.session["name"]      = name

    return RedirectResponse("/dashboard")


# ── Logout ────────────────────────────────────────────────────────────────────

@auth.get("/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")


# ── Helper: usuário atual ─────────────────────────────────────────────────────

def current_user(request: Request, db: Session = Depends(get_db)) -> dict | None:
    """
    Retorna dados do usuário logado com o plano atual.
    Retorna None se não houver sessão ativa.

    Como usar em rotas:

        @router.get("/dashboard")
        async def dashboard(
            request: Request,
            db:      Session = Depends(get_db),
        ):
            user = current_user(request, db)
            if not user:
                return RedirectResponse("/login")
    """
    google_id = request.session.get("google_id")
    if not google_id:
        return None

    repo = UserRepository(db)
    user = repo.get_by_google_id(google_id)
    if not user:
        return None

    # Busca o plano da subscription ativa (monthly ou annual)
    sub  = SubscriptionRepository(db).get_by_user_id(google_id)
    subscription_plan = (
        sub.plan if sub and sub.status == StatusSubPlains.active else None
    )

    return {
        "google_id":         google_id,
        "email":             request.session.get("email"),
        "name":              request.session.get("name"),
        "plan":              user.subplain,
        "subscription_plan": subscription_plan,  # "monthly" | "annual" | None
    }