import asyncio
import hashlib
import logging
import secrets
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.orm import Session, selectinload

from app.src.domain.models import Bot, BotSchedule, DeliveryJob, DeliveryJobStatus, PendingChatId, StatusBot
from app.src.infrabackend.config import (
    APP_TIMEZONE,
    BASE_URL,
    BOT_TOKEN_ALIASES,
    BOT_TOKEN_BY_VALUE,
    BOT_TOKENS,
    DELIVERY_JOB_MAX_ATTEMPTS,
    DELIVERY_JOB_RETRY_MINUTES,
)
from app.src.infrabackend.database import SessionLocal
from app.src.services.bot import Afilibot

logger = logging.getLogger(__name__)


def application_timezone() -> ZoneInfo:
    return ZoneInfo(APP_TIMEZONE)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def select_bot_token(user_id: str) -> str:
    if not BOT_TOKENS:
        raise RuntimeError("Nenhum token do Telegram configurado")
    digest = int(hashlib.sha256(user_id.encode("utf-8")).hexdigest(), 16)
    return BOT_TOKENS[digest % len(BOT_TOKENS)]


def bot_alias_for_token(bot_token: str) -> str:
    alias = BOT_TOKEN_BY_VALUE.get(bot_token)
    if not alias:
        raise RuntimeError("Token do Telegram sem alias configurado")
    return alias


def bot_token_for_alias(alias: str) -> str | None:
    return BOT_TOKEN_ALIASES.get(alias)


def parse_schedule_times(raw_values: list[str] | None, allow_multiple: bool) -> list[time]:
    tz = application_timezone()
    values = raw_values or []
    parsed: list[time] = []

    for raw in values:
        raw_value = (raw or "").strip()
        if not raw_value:
            continue
        hour_str, minute_str = raw_value.split(":", 1)
        run_time = time(hour=int(hour_str), minute=int(minute_str), tzinfo=tz)
        if run_time not in parsed:
            parsed.append(run_time)

    if not parsed:
        parsed = [time(hour=12, minute=0, tzinfo=tz)]

    parsed.sort(key=lambda item: (item.hour, item.minute))
    if allow_multiple:
        return parsed[:2]
    return parsed[:1]


def reserve_telegram_connection(db: Session, google_id: str, bot_token: str) -> PendingChatId:
    pending = db.query(PendingChatId).filter(PendingChatId.google_id == google_id).first()
    connection_code = secrets.token_urlsafe(12)
    expires_at = utc_now() + timedelta(minutes=15)

    if pending:
        pending.bot_token = bot_token
        pending.connection_code = connection_code
        pending.chat_id = None
        pending.expires_at = expires_at
        pending.connected_at = None
    else:
        pending = PendingChatId(
            google_id=google_id,
            bot_token=bot_token,
            connection_code=connection_code,
            chat_id=None,
            expires_at=expires_at,
        )
        db.add(pending)

    db.flush()
    return pending


def get_pending_connection(db: Session, google_id: str) -> PendingChatId | None:
    now = utc_now()
    return (
        db.query(PendingChatId)
        .filter(
            PendingChatId.google_id == google_id,
            PendingChatId.expires_at > now,
        )
        .first()
    )


def connect_chat_by_code(db: Session, connection_code: str, bot_token: str, chat_id: str) -> PendingChatId | None:
    now = utc_now()
    pending = (
        db.query(PendingChatId)
        .filter(
            PendingChatId.connection_code == connection_code,
            PendingChatId.bot_token == bot_token,
            PendingChatId.expires_at > now,
        )
        .first()
    )
    if not pending:
        return None

    pending.chat_id = chat_id
    pending.connected_at = now
    db.flush()
    return pending


async def fetch_bot_username(bot_token: str) -> str | None:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.telegram.org/bot{bot_token}/getMe",
                timeout=5,
            )
        if response.status_code == 200:
            return response.json().get("result", {}).get("username")
    except Exception:
        logger.exception("Erro ao buscar username do bot")
    return None


async def ensure_telegram_webhook(bot_token: str) -> None:
    alias = bot_alias_for_token(bot_token)
    webhook_url = f"{BASE_URL}/api/telegram/webhook/{alias}"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.telegram.org/bot{bot_token}/setWebhook",
            json={
                "url": webhook_url,
                "allowed_updates": ["message", "my_chat_member"],
            },
            timeout=10,
        )
    if response.status_code >= 300:
        raise RuntimeError("Não foi possível configurar o webhook do Telegram")


def sync_bot_schedules(db: Session, bot: Bot, schedule_times: list[time]) -> None:
    current_by_key = {
        (schedule.run_time.hour, schedule.run_time.minute): schedule
        for schedule in bot.schedules
    }
    wanted_keys = {(item.hour, item.minute) for item in schedule_times}

    for schedule in list(bot.schedules):
        key = (schedule.run_time.hour, schedule.run_time.minute)
        if key not in wanted_keys:
            db.delete(schedule)

    for schedule_time in schedule_times:
        key = (schedule_time.hour, schedule_time.minute)
        if key not in current_by_key:
            db.add(BotSchedule(bot_id=bot.id, run_time=schedule_time))

    if schedule_times:
        bot.time_to_sent = schedule_times[0]
    db.flush()


def enqueue_delivery_job(
    db: Session,
    bot: Bot,
    run_at: datetime,
    schedule_id: int | None = None,
    force: bool = False,
) -> DeliveryJob:
    existing = (
        db.query(DeliveryJob)
        .filter(
            DeliveryJob.bot_id == bot.id,
            DeliveryJob.schedule_id == schedule_id,
            DeliveryJob.run_at == run_at,
        )
        .first()
    )
    if existing and not force:
        return existing

    if existing and force:
        return existing

    job = DeliveryJob(
        bot_id=bot.id,
        schedule_id=schedule_id,
        run_at=run_at,
        status=DeliveryJobStatus.pending,
        max_attempts=DELIVERY_JOB_MAX_ATTEMPTS,
    )
    db.add(job)
    db.flush()
    return job


def enqueue_immediate_delivery(db: Session, bot: Bot) -> DeliveryJob:
    existing = (
        db.query(DeliveryJob)
        .filter(
            DeliveryJob.bot_id == bot.id,
            DeliveryJob.schedule_id.is_(None),
            DeliveryJob.status.in_([DeliveryJobStatus.pending, DeliveryJobStatus.running]),
        )
        .order_by(DeliveryJob.run_at.asc())
        .first()
    )
    if existing:
        return existing

    run_at = utc_now() + timedelta(seconds=5)
    return enqueue_delivery_job(db=db, bot=bot, run_at=run_at, schedule_id=None)


def schedule_bot_jobs(db: Session, reference: datetime | None = None) -> int:
    now = reference or utc_now()
    tz = application_timezone()
    local_now = now.astimezone(tz)
    created = 0

    bots = (
        db.query(Bot)
        .options(selectinload(Bot.schedules))
        .filter(Bot.status == StatusBot.active)
        .all()
    )

    for bot in bots:
        bot_created_local = bot.created_at.astimezone(tz) if bot.created_at else None
        bot_created_today = bool(bot_created_local and bot_created_local.date() == local_now.date())
        for schedule in bot.schedules:
            base_date = local_now.date() + timedelta(days=1) if bot_created_today else local_now.date()
            schedule_local = datetime.combine(
                base_date,
                time(hour=schedule.run_time.hour, minute=schedule.run_time.minute, tzinfo=tz),
                tzinfo=tz,
            )
            if schedule_local <= local_now:
                schedule_local = schedule_local + timedelta(days=1)
            run_at = schedule_local.astimezone(timezone.utc)

            existing = (
                db.query(DeliveryJob)
                .filter(
                    DeliveryJob.bot_id == bot.id,
                    DeliveryJob.schedule_id == schedule.id,
                    DeliveryJob.run_at == run_at,
                )
                .first()
            )
            if existing:
                continue
            enqueue_delivery_job(db=db, bot=bot, run_at=run_at, schedule_id=schedule.id)
            created += 1

    if created:
        db.commit()
    else:
        db.rollback()
    return created


def claim_due_job(db: Session) -> DeliveryJob | None:
    now = utc_now()
    query = (
        db.query(DeliveryJob)
        .options(
            selectinload(DeliveryJob.bot).selectinload(Bot.stores),
            selectinload(DeliveryJob.bot).selectinload(Bot.schedules),
        )
        .filter(
            DeliveryJob.status == DeliveryJobStatus.pending,
            DeliveryJob.run_at <= now,
        )
        .order_by(DeliveryJob.run_at.asc(), DeliveryJob.id.asc())
    )

    job = query.with_for_update(skip_locked=True).first()
    if not job:
        db.rollback()
        return None

    job.status = DeliveryJobStatus.running
    job.started_at = now
    job.attempts += 1
    db.commit()
    db.refresh(job)
    return job


async def process_delivery_job(job_id: int) -> None:
    with SessionLocal() as db:
        job = (
            db.query(DeliveryJob)
            .options(selectinload(DeliveryJob.bot).selectinload(Bot.stores))
            .filter(DeliveryJob.id == job_id)
            .first()
        )
        if not job or not job.bot:
            return

        bot = job.bot
        brands = [item.brand for item in bot.stores]
        affiliate_links = {
            item.brand: item.affiliate_link
            for item in bot.stores
            if item.affiliate_link
        }

    try:
        telegram_bot = Afilibot(bot_token=bot.bot_token, chat_id=bot.chat_id)
        result = await telegram_bot.send_promotions(
            brands=brands,
            affiliate_links=affiliate_links,
            default_affiliate_link=bot.affiliate_link,
        )
        sent_count = int(result.get("sent", 0))

        with SessionLocal() as db:
            job = db.query(DeliveryJob).filter(DeliveryJob.id == job_id).first()
            if not job:
                return
            job.status = DeliveryJobStatus.succeeded
            job.finished_at = utc_now()
            job.sent_count = sent_count
            job.last_error = None
            db.commit()
    except Exception as exc:
        with SessionLocal() as db:
            job = db.query(DeliveryJob).filter(DeliveryJob.id == job_id).first()
            if not job:
                return
            job.finished_at = utc_now()
            job.last_error = str(exc)
            if job.attempts >= job.max_attempts:
                job.status = DeliveryJobStatus.failed
            else:
                job.status = DeliveryJobStatus.pending
                job.run_at = utc_now() + timedelta(minutes=DELIVERY_JOB_RETRY_MINUTES)
            db.commit()


def run_scheduler_pass() -> int:
    with SessionLocal() as db:
        return schedule_bot_jobs(db)


async def run_worker_pass() -> int:
    processed = 0
    run_scheduler_pass()

    while True:
        with SessionLocal() as db:
            job = claim_due_job(db)
        if not job:
            break
        await process_delivery_job(job.id)
        processed += 1

    return processed


async def run_worker_loop(poll_seconds: float) -> None:
    while True:
        try:
            await run_worker_pass()
        except Exception:
            logger.exception("Erro no worker")
        await asyncio.sleep(poll_seconds)
