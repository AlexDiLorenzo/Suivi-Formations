"""Endpoints internes appelés par n8n (cron) pour les relances email.

Auth via header X-Internal-Secret (pas de JWT, pas de cookie). Pour
qu'un endpoint soit accessible, il faut REMINDERS_SECRET dans `.env`.
"""
import hashlib
import secrets as _secrets
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import verify_internal_secret
from app.models import (
    Document,
    DocumentRequest,
    DocumentType,
    DocumentVersion,
    DocumentVersionStatus,
    Driver,
    DriverRequiredDocument,
    DriverStatus,
    Reminder,
)
from app.schemas import (
    DueReminderItem,
    DueRemindersResponse,
    MarkSentRequest,
    SkippedReminderItem,
)


router = APIRouter(dependencies=[Depends(verify_internal_secret)])


REMINDER_TYPE_J90 = "j_minus_90"
REMINDER_TYPE_J30 = "j_minus_30"
REMINDER_TYPE_J7 = "j_minus_7"
REMINDER_TYPE_NEVER = "never_received"

MAGIC_LINK_TTL_DAYS = 7


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.get("/reminders/due", response_model=DueRemindersResponse)
def reminders_due(db: Annotated[Session, Depends(get_db)]):
    """Calcule les rappels a envoyer aujourd'hui, en cree les Reminders en
    base (sent_at=null) + DocumentRequests + magic_link, et retourne le
    payload pret pour n8n.

    Idempotent dans la journee : un (driver, doc_type, type) deja cree
    aujourd'hui n'est pas re-cree.
    """
    settings = get_settings()
    today = date.today()
    now = datetime.now(timezone.utc)
    today_start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    today_end = datetime.combine(today, datetime.max.time(), tzinfo=timezone.utc)

    drivers = (
        db.query(Driver)
        .filter(Driver.statut == DriverStatus.ACTIVE.value)
        .order_by(Driver.nom, Driver.prenom)
        .all()
    )
    if not drivers:
        return DueRemindersResponse(items=[], skipped=[])

    requirements_by_driver: dict[UUID, list[DriverRequiredDocument]] = defaultdict(list)
    for req in db.query(DriverRequiredDocument).all():
        requirements_by_driver[req.driver_id].append(req)

    doc_types_by_id = {dt.id: dt for dt in db.query(DocumentType).all()}

    current_by_pair: dict[tuple, DocumentVersion] = {
        (doc.driver_id, doc.document_type_id): ver
        for doc, ver in (
            db.query(Document, DocumentVersion)
            .outerjoin(DocumentVersion, Document.current_version_id == DocumentVersion.id)
            .all()
        )
        if ver is not None and ver.statut == DocumentVersionStatus.VALIDATED.value
    }

    today_reminders_keys: set[tuple] = {
        (r.driver_id, r.document_type_id, r.type)
        for r in db.query(Reminder)
        .filter(Reminder.scheduled_at >= today_start)
        .filter(Reminder.scheduled_at <= today_end)
        .all()
    }

    last_never_received: dict[tuple, datetime] = {}
    for r in (
        db.query(Reminder)
        .filter(Reminder.type == REMINDER_TYPE_NEVER)
        .order_by(Reminder.scheduled_at.desc())
        .all()
    ):
        key = (r.driver_id, r.document_type_id)
        if key not in last_never_received:
            last_never_received[key] = r.scheduled_at

    items: list[DueReminderItem] = []
    skipped: list[SkippedReminderItem] = []

    for driver in drivers:
        for req in requirements_by_driver.get(driver.id, []):
            dt = doc_types_by_id.get(req.document_type_id)
            if not dt:
                continue

            current = current_by_pair.get((driver.id, req.document_type_id))
            type_to_send: str | None = None
            days_until: int | None = None

            if current is not None:
                days_until = (current.date_peremption - today).days
                if days_until == 90:
                    type_to_send = REMINDER_TYPE_J90
                elif days_until == 30:
                    type_to_send = REMINDER_TYPE_J30
                elif days_until == 7:
                    type_to_send = REMINDER_TYPE_J7
            else:
                grace = settings.never_received_grace_days
                interval = settings.never_received_interval_days
                if (today - req.required_since).days >= grace:
                    last = last_never_received.get((driver.id, req.document_type_id))
                    elapsed_days = (now - last).days if last else None
                    if last is None or elapsed_days >= interval:
                        type_to_send = REMINDER_TYPE_NEVER

            if type_to_send is None:
                continue

            if (driver.id, req.document_type_id, type_to_send) in today_reminders_keys:
                continue

            if not driver.email:
                skipped.append(
                    SkippedReminderItem(
                        driver_id=driver.id,
                        driver_nom=f"{driver.nom} {driver.prenom}",
                        document_type_code=dt.code,
                        type=type_to_send,
                        reason="no_email",
                    )
                )
                continue

            token = _secrets.token_urlsafe(32)
            doc_request = DocumentRequest(
                driver_id=driver.id,
                document_type_id=req.document_type_id,
                token_hash=_hash_token(token),
                expires_at=now + timedelta(days=MAGIC_LINK_TTL_DAYS),
            )
            db.add(doc_request)

            reminder = Reminder(
                driver_id=driver.id,
                document_type_id=req.document_type_id,
                document_version_id=current.id if current else None,
                type=type_to_send,
                scheduled_at=now,
                channel="email",
            )
            db.add(reminder)
            db.flush()

            items.append(
                DueReminderItem(
                    reminder_id=reminder.id,
                    type=type_to_send,
                    driver_email=driver.email,
                    driver_prenom=driver.prenom,
                    driver_nom=driver.nom,
                    document_type_code=dt.code,
                    document_type_libelle=dt.libelle,
                    days_until_expiry=days_until,
                    date_peremption=current.date_peremption if current else None,
                    magic_link=f"{settings.frontend_base_url.rstrip('/')}/upload/{token}",
                    magic_link_expires_at=doc_request.expires_at,
                )
            )

    db.commit()
    return DueRemindersResponse(items=items, skipped=skipped)


@router.post("/reminders/mark-sent")
def reminders_mark_sent(payload: MarkSentRequest, db: Annotated[Session, Depends(get_db)]):
    """Appele par n8n apres l'envoi des emails pour cocher sent_at."""
    now = datetime.now(timezone.utc)
    updated = 0
    for reminder_id in payload.reminder_ids:
        r = db.get(Reminder, reminder_id)
        if r and r.sent_at is None:
            r.sent_at = now
            updated += 1
    db.commit()
    return {"updated": updated}
