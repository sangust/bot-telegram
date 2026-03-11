import hashlib
import hmac
import logging
from datetime import datetime, timezone, timedelta
import httpx
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.api.routes.auth import current_user
from app.src.domain.models import Payment, PaymentMethod, PlanType, StatusSubPlains, SubPlains, User
from app.src.infrabackend.config import (
    BASE_URL,
    MERCADOPAGO_ACCESS_TOKEN,
    MERCADOPAGO_API_URL,
    MERCADOPAGO_CURRENCY_ID,
    MERCADOPAGO_WEBHOOK_SECRET,
)
from app.src.infrabackend.database import get_db
from app.src.infrabackend.repository import SubscriptionRepository
from app.src.infrabackend.schemas import CheckoutRequestSchema
import mercadopago

logger    = logging.getLogger(__name__)
templates = Jinja2Templates("app/templates")
subscription = APIRouter(tags=["subscription"])

PLANS = {
    PlanType.monthly: {
        "name":         "afilibot — Plano Mensal",
        "amount_reais": 14.99,
        "days":         30,
    },
    PlanType.annual: {
        "name":         "afilibot — Plano Anual",
        "amount_reais": 149.99,
        "days":         365,
    },
}


def _mercadopago_headers(include_json: bool = True) -> dict[str, str]:
    if not MERCADOPAGO_ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail="Mercado Pago não configurado")
    headers = {"Authorization": f"Bearer {MERCADOPAGO_ACCESS_TOKEN}"}
    if include_json:
        headers["Content-Type"] = "application/json"
    return headers


def _parse_mp_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_mp_signature(signature_header: str) -> tuple[str | None, str | None]:
    values: dict[str, str] = {}
    for part in signature_header.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        values[key.strip()] = value.strip()
    return values.get("ts"), values.get("v1")


def _validate_mp_signature(request: Request, data_id: str | None) -> bool:
    if not MERCADOPAGO_WEBHOOK_SECRET:
        return True

    signature_header = request.headers.get("x-signature", "")
    request_id = request.headers.get("x-request-id", "")
    ts, signature = _parse_mp_signature(signature_header)

    if not ts or not signature or not request_id or not data_id:
        return False

    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    digest = hmac.new(
        MERCADOPAGO_WEBHOOK_SECRET.encode(),
        msg=manifest.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, signature)


def _extract_notification_id(payload: dict, request: Request) -> str | None:
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    for candidate in (
        data.get("id"),
        payload.get("id") if isinstance(payload, dict) else None,
        request.query_params.get("data.id"),
        request.query_params.get("id"),
    ):
        if candidate:
            return str(candidate)

    resource = payload.get("resource") if isinstance(payload, dict) else None
    if isinstance(resource, str):
        resource_id = resource.rstrip("/").split("/")[-1]
        if resource_id:
            return resource_id
    return None


async def _get_mp_payment(payment_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{MERCADOPAGO_API_URL}/v1/payments/{payment_id}",
            headers=_mercadopago_headers(include_json=False),
            timeout=20.0,
        )
    if response.status_code != 200:
        logger.error(
            "Erro Mercado Pago ao consultar pagamento %s: %s",
            payment_id,
            response.text,
        )
        raise HTTPException(
            status_code=502,
            detail="Erro ao consultar pagamento no Mercado Pago.",
        )
    return response.json()


def _payment_method_from_mp(mp_payment: dict) -> PaymentMethod | None:
    payment_method_id = (mp_payment.get("payment_method_id") or "").lower()
    payment_type_id = (mp_payment.get("payment_type_id") or "").lower()

    if payment_method_id == "pix" or payment_type_id == "bank_transfer":
        return PaymentMethod.pix

    if payment_type_id in {"credit_card", "debit_card", "prepaid_card"}:
        return PaymentMethod.card

    return None


def _payment_user_id(mp_payment: dict) -> str | None:
    metadata = mp_payment.get("metadata") or {}
    for candidate in (mp_payment.get("external_reference"), metadata.get("user_id")):
        if candidate:
            return str(candidate)
    return None


def _record_payment_once(db: Session, subscription) -> None:
    existing = (
        db.query(Payment)
        .filter(Payment.billing_id == subscription.billing_id)
        .first()
    )
    if not existing:
        SubscriptionRepository(db).record_payment(subscription)


def _sync_local_subscription(db: Session, subscription, mp_payment: dict) -> None:
    status = (mp_payment.get("status") or "").lower()
    plan_cfg = PLANS.get(subscription.plan, {})
    now = datetime.now(timezone.utc)
    user_obj = db.query(User).filter(User.google_id == subscription.user_id).first()

    amount = mp_payment.get("transaction_amount")
    if amount is not None:
        try:
            subscription.amount = int(round(float(amount) * 100))
        except (TypeError, ValueError):
            pass

    payer = mp_payment.get("payer") or {}
    payer_id = payer.get("id")
    if payer_id is not None:
        subscription.customer_id = str(payer_id)

    payment_method = _payment_method_from_mp(mp_payment)
    if payment_method is not None:
        subscription.payment_method = payment_method

    if status in {"approved", "authorized"}:
        approved_at = (
            _parse_mp_datetime(mp_payment.get("date_approved"))
            or _parse_mp_datetime(mp_payment.get("date_created"))
            or now
        )
        subscription.status = StatusSubPlains.active
        subscription.start = subscription.start or approved_at
        subscription.next_payment = approved_at + timedelta(days=plan_cfg.get("days", 30))
        subscription.canceled_at = None
        if user_obj:
            user_obj.subplain = SubPlains.premium
        _record_payment_once(db, subscription)
        return

    if status in {"pending", "in_process", "in_mediation"}:
        subscription.status = StatusSubPlains.pending
        return

    if status in {"cancelled", "rejected", "refunded", "charged_back"}:
        subscription.status = StatusSubPlains.canceled
        subscription.canceled_at = _parse_mp_datetime(mp_payment.get("date_last_updated")) or now
        subscription.next_payment = None
        if user_obj:
            user_obj.subplain = SubPlains.free
        return

    logger.info("Status Mercado Pago não mapeado: %s", status)


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
        "items": [{
            "id": body.plan,
            "title": plan["name"],
            "description": "Automação de afiliados",
            "quantity": 1,
            "currency_id": MERCADOPAGO_CURRENCY_ID,
            "unit_price": plan["amount_reais"],
        }],
        "external_reference": user["google_id"],
        "payer": {
            "email": user["email"],
        },
        "notification_url": f"{BASE_URL}/api/subscription/webhook",
        "back_urls": {
            "success": f"{BASE_URL}/subscription?payment=success",
            "failure": f"{BASE_URL}/subscription?payment=failure",
            "pending": f"{BASE_URL}/subscription?payment=loading",
        },
        "auto_return": "approved",
        "metadata": {
            "user_id": user["google_id"],
            "plan": body.plan,
        },
    }

    payment = mercadopago.SDK.preference().create(payload)
    url_preference = payment["response"]["init_point"]
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url_preference,
            json=payload,
            headers=_mercadopago_headers(),
            timeout=15.0,
        )

    if response.status_code not in (200, 201):
        logger.error("Erro Mercado Pago checkout: %s", response.text)
        raise HTTPException(status_code=502, detail="Erro ao criar checkout.")

    checkout = response.json()
    billing_id = checkout.get("id")
    url = checkout.get("init_point") or checkout.get("sandbox_init_point")

    if not billing_id:
        raise HTTPException(status_code=502, detail="Mercado Pago não retornou id do checkout")

    if not url:
        raise HTTPException(status_code=502, detail="Mercado Pago não retornou URL de pagamento")

    repo = SubscriptionRepository(db)
    try:
        repo.create_or_update_pending(
            user_id    = user["google_id"],
            billing_id = billing_id,
            plan       = body.plan,
            amount     = plan["amount_cents"],
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Erro ao salvar subscription pending")
        raise HTTPException(status_code=500, detail="Erro interno ao salvar checkout.")

    return {"payment_url": url}


# ── Webhook ───────────────────────────────────────────────────────────────────

@subscription.post("/api/subscription/webhook")
async def mercadopago_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        event = await request.json()
    except Exception:
        event = {}

    billing_id = _extract_notification_id(event, request)
    if not billing_id:
        logger.warning("Webhook Mercado Pago sem identificador")
        return {"received": True}

    if not _validate_mp_signature(request, billing_id):
        raise HTTPException(status_code=401, detail="Assinatura inválida")

    event_type = request.query_params.get("type") or event.get("type")
    if event_type and event_type != "payment":
        return {"received": True}

    mp_payment = await _get_mp_payment(billing_id)

    repo = SubscriptionRepository(db)
    sub = repo.get_by_billing_id(billing_id)
    if not sub:
        user_id = _payment_user_id(mp_payment)
        if user_id:
            sub = repo.get_by_user_id(user_id)

    if not sub:
        logger.warning("Webhook para billing_id desconhecido: %s", billing_id)
        return {"received": True}

    try:
        sub.billing_id = billing_id
        _sync_local_subscription(db, sub, mp_payment)
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

    if not sub or sub.status not in {StatusSubPlains.active, StatusSubPlains.pending}:
        raise HTTPException(status_code=404, detail="Nenhuma assinatura ativa")

    now             = datetime.now(timezone.utc)
    sub.status      = StatusSubPlains.canceled
    sub.canceled_at = now
    sub.next_payment = None

    user_obj = db.query(User).filter(User.google_id == user["google_id"]).first()
    if user_obj:
        user_obj.subplain = SubPlains.free

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro ao salvar cancelamento.")

    return {"canceled": True}