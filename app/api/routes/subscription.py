import json
import logging
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.src.infrabackend.database import get_db
from app.src.infrabackend.repository import SubscriptionRepository
from app.src.infrabackend.schemas import CheckoutRequestSchema
from app.src.domain.models import User, Subscription, StatusSubPlains, SubPlains, PlanType
from app.src.infrabackend.config import (
    ABACATEPAY_API_KEY,
    ABACATEPAY_API_URL,
    ABACATEPAY_WEBHOOK_SECRET,
    BASE_URL,
)
from app.api.routes.auth import current_user

logger    = logging.getLogger(__name__)
templates = Jinja2Templates("app/templates")
subscription = APIRouter(tags=["subscription"])

PLANS = {
    PlanType.monthly: {
        "externalId": "prod_CXDmgttsELW0YG4g35Wwk1NA",
        "name":       "afilibot — Plano Mensal",
        "price":      1499,
        "days":       30,
        "frequency":  "MULTIPLE_PAYMENTS",
    },
    PlanType.annual: {
        "externalId": "prod_YKJh0WgxMcZmk4Q5uMeaNF5F",
        "name":       "afilibot — Plano Anual",
        "price":      14999,
        "days":       365,
        "frequency":  "MULTIPLE_PAYMENTS",
    },
}


# ── Página ────────────────────────────────────────────────────────────────────

@subscription.get("/subscription")
async def subscription_page(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/")
    return templates.TemplateResponse("subscription.html", {"request": request})


# ── Status ────────────────────────────────────────────────────────────────────

@subscription.get("/api/subscription/status")
async def subscription_status(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    repo = SubscriptionRepository(db)
    sub  = repo.get_by_user_id(user["google_id"])
    if not sub:
        return {"has_subscription": False}

    return {
        "has_subscription": True,
        "status":       sub.status,
        "plan":         sub.plan,
        "next_payment": sub.next_payment.isoformat() if sub.next_payment else None,
        "canceled_at":  sub.canceled_at.isoformat()  if sub.canceled_at  else None,
    }


# ── Checkout ──────────────────────────────────────────────────────────────────

@subscription.post("/api/subscription/checkout")
async def create_checkout(
    request: Request,
    body:    CheckoutRequestSchema,
    db:      Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    plan = PLANS.get(body.plan)
    if not plan:
        raise HTTPException(status_code=400, detail="Plano inválido")

    payload = {
        "frequency": plan["frequency"],
        "methods":   ["PIX", "CARD"],
        "customer": {
            "name":  user["name"],
            "email": user["email"],
            "taxId": "090.088.411-85",
            "cellphone": "(11) 4002-8922"
        },
        "products": [{
            "externalId":  plan["externalId"],
            "name":        plan["name"],
            "quantity":    1,
            "price":       plan["price"],
            "description": "Automação de afiliados",
        }],
        # Secret removido da query string — qualquer pessoa que veja os logs da URL conseguia forjar webhooks
        # O AbacatePay deve validar via HMAC no header (ver webhook abaixo)
        "webhookUrl":    f"{BASE_URL}/api/subscription/webhook",
        "completionUrl": f"{BASE_URL}/createbot?payment=success",
        "returnUrl":     f"{BASE_URL}/",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{ABACATEPAY_API_URL}/billing/create",
            json=payload,
            headers={
                "Authorization": f"Bearer {ABACATEPAY_API_KEY}",
                "Content-Type":  "application/json",
            },
            timeout=15.0,
        )

    if response.status_code != 200:
        logger.error("Erro AbacatePay checkout: %s", response.text)
        raise HTTPException(status_code=502, detail="Erro ao criar checkout.")

    billing    = response.json().get("data", {})
    billing_id = billing.get("id")
    url        = billing.get("url")

    if not billing_id:
        raise HTTPException(status_code=502, detail="AbacatePay não retornou billing_id")

    repo = SubscriptionRepository(db)
    try:
        repo.create_or_update_pending(
            user_id    = user["google_id"],
            billing_id = billing_id,
            plan       = body.plan,
            amount     = plan["price"],
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Erro ao salvar subscription pending")
        raise HTTPException(status_code=500, detail="Erro interno ao salvar checkout.")

    return {"payment_url": url}


# ── Webhook ───────────────────────────────────────────────────────────────────

@subscription.post("/api/subscription/webhook")
async def abacatepay_webhook(request: Request, db: Session = Depends(get_db)):
    # Valida o secret pelo header em vez de query string
    # Se o AbacatePay ainda não suportar header, troque pela linha comentada abaixo
    webhook_secret = request.headers.get("x-webhook-secret", "")
    # webhook_secret = request.query_params.get("webhookSecret", "")  # fallback temporário

    if webhook_secret != ABACATEPAY_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Assinatura inválida")

    try:
        event = json.loads(await request.body())
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Payload inválido")

    event_type  = event.get("event")
    billing     = event.get("data", {}).get("billing", {})
    payment     = event.get("data", {}).get("payment", {})
    billing_id  = billing.get("id")
    customer_id = billing.get("customer", {}).get("id")

    if not billing_id:
        raise HTTPException(status_code=400, detail="billing_id ausente")

    repo = SubscriptionRepository(db)
    sub  = repo.get_by_billing_id(billing_id)

    if not sub:
        # Billing de outro ambiente (staging vs prod) — ignora sem erro
        logger.warning("Webhook para billing_id desconhecido: %s", billing_id)
        return {"received": True}

    try:
        user_obj = db.query(User).filter(User.google_id == sub.user_id).first()
        plan_cfg = PLANS.get(sub.plan, {})
        now      = datetime.now(timezone.utc)

        if event_type == "billing.paid":
            sub.status         = StatusSubPlains.active
            sub.customer_id    = customer_id
            sub.payment_method = payment.get("method")
            sub.amount         = billing.get("amount", sub.amount)
            sub.start          = now
            sub.next_payment   = now + timedelta(days=plan_cfg.get("days", 30))
            sub.canceled_at    = None
            if user_obj:
                user_obj.subplain = SubPlains.premium
            repo.record_payment(sub)

        elif event_type == "billing.canceled":
            sub.status      = StatusSubPlains.canceled
            sub.canceled_at = now
            if user_obj:
                user_obj.subplain = SubPlains.free

        elif event_type == "billing.expired":
            sub.status = StatusSubPlains.expired
            if user_obj:
                user_obj.subplain = SubPlains.free

        else:
            logger.info("Evento desconhecido: %s", event_type)

        db.commit()
        return {"received": True}

    except Exception:
        db.rollback()
        logger.exception("Erro ao processar webhook billing_id=%s", billing_id)
        raise HTTPException(status_code=500, detail="Erro interno ao processar webhook.")


# ── Cancelar ──────────────────────────────────────────────────────────────────

@subscription.post("/api/subscription/cancel")
async def cancel_subscription(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    repo = SubscriptionRepository(db)
    sub  = repo.get_by_user_id(user["google_id"])

    if not sub or sub.status != StatusSubPlains.active:
        raise HTTPException(status_code=404, detail="Nenhuma assinatura ativa")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{ABACATEPAY_API_URL}/billing/{sub.billing_id}/cancel",
            headers={"Authorization": f"Bearer {ABACATEPAY_API_KEY}"},
            timeout=15.0,
        )

    if response.status_code not in (200, 204):
        logger.error("Erro ao cancelar no AbacatePay: %s", response.text)
        raise HTTPException(status_code=502, detail="Erro ao cancelar no AbacatePay")

    now             = datetime.now(timezone.utc)
    sub.status      = StatusSubPlains.canceled
    sub.canceled_at = now

    user_obj = db.query(User).filter(User.google_id == user["google_id"]).first()
    if user_obj:
        user_obj.subplain = SubPlains.free

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro ao salvar cancelamento.")

    return {"canceled": True}