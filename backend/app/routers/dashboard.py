from collections import Counter
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_admin
from app.models import (
    Document,
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

    counter: Counter = Counter()
    out_drivers: list[DashboardDriver] = []

    for driver in drivers:
        cells: list[DashboardCell] = []
        for dt in doc_types:
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
