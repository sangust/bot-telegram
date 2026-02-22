import os
from datetime import date

import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from app.src.infrabackend.database import LocalDatabase
from app.src.domain.models import User

auth = APIRouter(tags=["auth"])
templates = Jinja2Templates("app/templates")

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")

_GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO  = "https://www.googleapis.com/oauth2/v3/userinfo"

_SCOPES = "openid email profile"



@auth.get("/login")
async def login_page(request: Request):
    """
    Serve o HTML da tela de login.
    Se o usuário já estiver logado, redireciona direto pro dashboard.
    """
    if current_user(request):
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse("login.html", {"request": request})


# ── Redirect para o Google ────────────────────────────────────────────────────

@auth.get("/auth/login")
async def login_redirect():
    """
    Monta a URL de autenticação do Google e redireciona o usuário.
    Disparado quando o usuário clica em "Entrar com Google".
    """
    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         _SCOPES,
        "access_type":   "offline",
        "prompt":        "select_account",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(f"{_GOOGLE_AUTH_URL}?{query}")


# ── Callback do Google ────────────────────────────────────────────────────────

@auth.get("/auth/callback")
async def callback(request: Request, code: str):
    """
    O Google redireciona aqui depois que o usuário autoriza o acesso.
    Fluxo: code → access_token → dados do usuário → upsert no banco → sessão → dashboard.
    """
    # 1. Troca o code temporário por um access_token real
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code":          code,
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri":  GOOGLE_REDIRECT_URI,
                "grant_type":    "authorization_code",
            },
        )

    if token_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Falha ao obter token do Google.")

    access_token = token_response.json().get("access_token")

    # 2. Usa o access_token para buscar os dados do usuário logado
    async with httpx.AsyncClient() as client:
        userinfo_response = await client.get(
            _GOOGLE_USERINFO,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if userinfo_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Falha ao buscar dados do usuário.")

    userinfo  = userinfo_response.json()
    google_id = userinfo.get("sub")    # ID único e permanente do usuário no Google
    email     = userinfo.get("email")
    name      = userinfo.get("name")

    if not google_id or not email:
        raise HTTPException(status_code=400, detail="Dados insuficientes retornados pelo Google.")

    # 3. Cria o usuário no banco se for a primeira vez, ou atualiza o nome
    db      = LocalDatabase()
    session = db.SESSION()

    try:
        user = session.query(User).filter(User.google_id == google_id).first()

        if not user:
            user = User(
                google_id  = google_id,
                email      = email,
                name       = name,
                created_at = date.today(),
            )
            session.add(user)
        else:
            user.name = name  # atualiza caso tenha mudado no Google

        session.commit()

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao salvar usuário: {e}")

    finally:
        session.close()
    request.session["google_id"] = google_id
    request.session["email"]     = email
    request.session["name"]      = name

    return RedirectResponse("/dashboard")


# ── Logout ────────────────────────────────────────────────────────────────────

@auth.get("/auth/logout")
async def logout(request: Request):
    """Limpa a sessão e manda o usuário de volta pra landing page."""
    request.session.clear()
    return RedirectResponse("/")


# ── Helper: usuário atual ─────────────────────────────────────────────────────

def current_user(request: Request) -> dict | None:
    """
    Retorna os dados do usuário logado a partir da sessão.
    Retorna None se não houver sessão ativa.

    Como usar em qualquer rota que precise de autenticação:

        from app.api.routes.auth import current_user

        @router.get("/dashboard")
        async def dashboard(request: Request):
            user = current_user(request)
            if not user:
                return RedirectResponse("/login")
            ...
    """
    google_id = request.session.get("google_id")
    if not google_id:
        return None

    return {
        "google_id": google_id,
        "email":     request.session.get("email"),
        "name":      request.session.get("name"),
    }