from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_admin
from app.models import (
    Document,
    DocumentRequest,
    DocumentType,
    DocumentVersion,
    DocumentVersionStatus,
    Driver,
    DriverRequiredDocument,
    DriverStatus,
)
from app.schemas import (
    CellRedReason,
    CellStatus,
    DashboardCell,
    DashboardDocType,
    DashboardDriver,
    DashboardResponse,
    DashboardSummary,
)


router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get("", response_model=DashboardResponse)
def get_dashboard(db: Annotated[Session, Depends(get_db)]):
    settings = get_settings()
    today = date.today()
    orange_threshold = today + timedelta(days=settings.orange_threshold_days)

    doc_types = (
        db.query(DocumentType)
        .order_by(DocumentType.display_order, DocumentType.code)
        .all()
    )
    drivers = (
        db.query(Driver)
        .filter(Driver.statut == DriverStatus.ACTIVE.value)
        .order_by(Driver.nom, Driver.prenom)
        .all()
    )

    applicable_set: set[tuple] = {
        (r.driver_id, r.document_type_id)
        for r in db.query(DriverRequiredDocument).all()
    }

    current_version_by_pair: dict[tuple, DocumentVersion] = {
        (doc.driver_id, doc.document_type_id): version
        for doc, version in (
            db.query(Document, DocumentVersion)
            .outerjoin(DocumentVersion, Document.current_version_id == DocumentVersion.id)
            .all()
        )
        if version is not None
        and version.statut == DocumentVersionStatus.VALIDATED.value
    }

    pending_by_pair: dict[tuple, UUID] = {}
    for doc, ver in (
        db.query(Document, DocumentVersion)
        .join(DocumentVersion, DocumentVersion.document_id == Document.id)
        .filter(DocumentVersion.statut == DocumentVersionStatus.PENDING.value)
        .order_by(DocumentVersion.uploaded_at.desc())
        .all()
    ):
        pending_by_pair.setdefault((doc.driver_id, doc.document_type_id), ver.id)

    now = datetime.now(timezone.utc)
    open_request_by_pair: dict[tuple, datetime] = {}
    for req in (
        db.query(DocumentRequest)
        .filter(DocumentRequest.consumed_at.is_(None))
        .filter(DocumentRequest.expires_at > now)
        .order_by(DocumentRequest.created_at.desc())
        .all()
    ):
        open_request_by_pair.setdefault((req.driver_id, req.document_type_id), req.created_at)

    counter: Counter = Counter()
    out_drivers: list[DashboardDriver] = []

    for driver in drivers:
        cells: list[DashboardCell] = []
        for dt in doc_types:
            pending_id = pending_by_pair.get((driver.id, dt.id))
            has_pending = pending_id is not None
            open_request_at = open_request_by_pair.get((driver.id, dt.id))
            if (driver.id, dt.id) not in applicable_set:
                cells.append(DashboardCell(document_type_id=dt.id, status=CellStatus.GREY))
                counter[CellStatus.GREY] += 1
                continue

            current = current_version_by_pair.get((driver.id, dt.id))
            if current is None:
                cells.append(
                    DashboardCell(
                        document_type_id=dt.id,
                        status=CellStatus.RED,
                        reason=CellRedReason.NEVER_RECEIVED,
                        has_pending_version=has_pending,
                        pending_version_id=pending_id,
                        open_request_sent_at=open_request_at,
                    )
                )
                counter[CellStatus.RED] += 1
                continue

            days = (current.date_peremption - today).days
            if days < 0:
                status_value = CellStatus.RED
                reason = CellRedReason.EXPIRED
            elif current.date_peremption <= orange_threshold:
                status_value = CellStatus.ORANGE
                reason = None
            else:
                status_value = CellStatus.GREEN
                reason = None

            cells.append(
                DashboardCell(
                    document_type_id=dt.id,
                    status=status_value,
                    reason=reason,
                    date_peremption=current.date_peremption,
                    days_until_expiry=days,
                    current_version_id=current.id,
                    has_pending_version=has_pending,
                    pending_version_id=pending_id,
                    open_request_sent_at=open_request_at,
                )
            )
            counter[status_value] += 1

        out_drivers.append(
            DashboardDriver(
                id=driver.id,
                prenom=driver.prenom,
                nom=driver.nom,
                statut=driver.statut,
                cells=cells,
            )
        )

    summary = DashboardSummary(
        by_status={
            CellStatus.GREEN: counter[CellStatus.GREEN],
            CellStatus.ORANGE: counter[CellStatus.ORANGE],
            CellStatus.RED: counter[CellStatus.RED],
            CellStatus.GREY: counter[CellStatus.GREY],
        }
    )

    return DashboardResponse(
        doc_types=[DashboardDocType.model_validate(dt) for dt in doc_types],
        drivers=out_drivers,
        summary=summary,
    )
