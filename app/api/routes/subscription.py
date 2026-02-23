import json
import hmac
import hashlib
from datetime import date, timedelta

import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.src.domain.models import User, Subscription, StatusSubPlains, SubPlains
from app.src.infrabackend.database import LocalDatabase
from app.src.infrabackend.config import ABACATEPAY_API_KEY, ABACATEPAY_API_URL, BASE_URL
from app.api.routes.auth import current_user

templates = Jinja2Templates("app/templates")
subscription = APIRouter(tags=["subscription"])

PLANS = {
    "monthly": {
        "externalId": "prod_CXDmgttsELW0YG4g35Wwk1NA",
        "name":       "afilibot — Plano Mensal",
        "price":      1499,
        "days":       30,
        "frequency":  "MULTIPLE_PAYMENTS",
    },
    "annual": {
        "name":       "afilibot — Plano Anual",
        "price":      14999,
        "days":       365,
        "frequency":  "MULTIPLE_PAYMENTS",
    },
}


class CheckoutRequest(BaseModel):
    plan: str


@subscription.get("/subscription")
async def subscription_page(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/")
    return templates.TemplateResponse("subscription.html", {"request": request})


@subscription.get("/api/subscription/status")
async def subscription_status(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    db = LocalDatabase()
    session = db.SESSION()
    try:
        sub = (
            session.query(Subscription)
            .filter(Subscription.user_id == user["google_id"])
            .order_by(Subscription.id.desc())
            .first()
        )

        if not sub:
            return {"has_subscription": False, "status": None}

        return {
            "has_subscription": True,
            "status":       sub.status,
            "plan":         sub.plan,
            "next_payment": str(sub.next_payment) if sub.next_payment else None,
            "canceled_at":  str(sub.canceled_at)  if sub.canceled_at  else None,
        }
    finally:
        session.close()


@subscription.post("/api/subscription/checkout")
async def create_checkout(request: Request, body: CheckoutRequest):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    plan = PLANS.get(body.plan)
    if not plan:
        raise HTTPException(status_code=400, detail="Plano inválido")

    payload = {
        "frequency": plan["frequency"],
        "methods": ["PIX", "CARD"],
        "customer": {
            "name":      user["name"],
            "email":     user["email"],
            "cellphone": "(11) 4002-8922",
            "taxId":     "090.088.411-85",
        },
        "products": [
            {
                "externalId":  plan["externalId"],
                "name":        plan["name"],
                "quantity":    1,
                "price":       plan["price"],
                "description": "Bot de promocoes",
            }
        ],
        "metadata": {
            "google_id": user["google_id"],
            "plan":      body.plan,
        },
        "webhookUrl":    f"{BASE_URL}/api/subscription/webhook",
        "completionUrl": f"{BASE_URL}/createbot?payment=success",
        "returnUrl":     f"{BASE_URL}/subscription",
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
        raise HTTPException(status_code=502, detail=f"Erro ao criar cobrança: {response.text}")

    data = response.json()
    billing = data.get("data", {})
    return {"payment_url": billing.get("url")}


@subscription.post("/api/subscription/webhook")
async def abacatepay_webhook(request: Request):
    body_bytes = await request.body()

    signature_header = request.headers.get("x-abacatepay-signature", "")
    expected = hmac.new(
        key=ABACATEPAY_API_KEY.encode(),
        msg=body_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature_header, expected):
        raise HTTPException(status_code=401, detail="Assinatura inválida")

    try:
        event = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Payload inválido")

    event_type = event.get("event")
    billing    = event.get("data", {})
    metadata   = billing.get("metadata", {})
    google_id  = metadata.get("google_id")
    plan_key   = metadata.get("plan")
    billing_id = billing.get("id")

    if not google_id or not plan_key:
        raise HTTPException(status_code=400, detail="Metadata incompleto")

    plan = PLANS.get(plan_key)
    if not plan:
        raise HTTPException(status_code=400, detail="Plano desconhecido")

    db = LocalDatabase()
    session = db.SESSION()
    try:
        sub = (
            session.query(Subscription)
            .filter(Subscription.abacatepay_id == billing_id)
            .first()
        )

        if event_type == "billing.paid":
            today = date.today()
            if sub:
                sub.status       = StatusSubPlains.active
                sub.next_payment = today + timedelta(days=plan["days"])
                sub.canceled_at  = None
            else:
                sub = Subscription(
                    user_id       = google_id,
                    abacatepay_id = billing_id,
                    status        = StatusSubPlains.active,
                    plan          = plan_key,
                    value         = plan["price"] / 100,
                    start         = today,
                    next_payment  = today + timedelta(days=plan["days"]),
                )
                session.add(sub)

            user_obj = session.query(User).filter(User.google_id == google_id).first()
            if user_obj:
                user_obj.subplain = SubPlains.basic

        elif event_type == "billing.canceled":
            if sub:
                sub.status      = StatusSubPlains.canceled
                sub.canceled_at = date.today()
            user_obj = session.query(User).filter(User.google_id == google_id).first()
            if user_obj:
                user_obj.subplain = SubPlains.free

        elif event_type == "billing.expired":
            if sub:
                sub.status = StatusSubPlains.expired
            user_obj = session.query(User).filter(User.google_id == google_id).first()
            if user_obj:
                user_obj.subplain = SubPlains.free

        session.commit()
        return {"received": True}

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@subscription.post("/api/subscription/cancel")
async def cancel_subscription(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    db = LocalDatabase()
    session = db.SESSION()
    try:
        sub = (
            session.query(Subscription)
            .filter(
                Subscription.user_id == user["google_id"],
                Subscription.status  == StatusSubPlains.active,
            )
            .first()
        )

        if not sub:
            raise HTTPException(status_code=404, detail="Nenhuma assinatura ativa encontrada")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ABACATEPAY_API_URL}/billing/{sub.abacatepay_id}/cancel",
                headers={"Authorization": f"Bearer {ABACATEPAY_API_KEY}"},
                timeout=15.0,
            )

        if response.status_code not in (200, 204):
            raise HTTPException(status_code=502, detail="Erro ao cancelar no AbacatePay")

        sub.status      = StatusSubPlains.canceled
        sub.canceled_at = date.today()

        user_obj = session.query(User).filter(User.google_id == user["google_id"]).first()
        if user_obj:
            user_obj.subplain = SubPlains.free

        session.commit()
        return {"canceled": True}

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()