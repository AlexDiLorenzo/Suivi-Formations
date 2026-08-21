"""Consultation des depanneurs — en lecture seule, sans exception.

Rien ne se modifie ici. La liste est le reflet de l'equipe tenue dans DepanTime
et dans Flotte (cf. app/sync_depantime.py) : identite, statut, equipe, type de
vehicule et interim y sont reecrits a chaque synchronisation. Ce qu'on attend
de chacun en decoule (cf. app/socle.py) au lieu de se cocher — l'ancien reglage
manuel de l'applicabilite derivait des la premiere mutation oubliee, et le
niveau d'exigence, lui, appartient au seed des types.

Cette application ne detient que les documents eux-memes.
"""
from collections import defaultdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_admin
from app.models import Driver, DriverRequiredDocument, DriverStatus
from app.schemas import DriverOut


router = APIRouter(dependencies=[Depends(get_current_admin)])


def _serialize(driver: Driver, doctype_ids: list[UUID]) -> DriverOut:
    return DriverOut(
        id=driver.id,
        prenom=driver.prenom,
        nom=driver.nom,
        email=driver.email,
        telephone=driver.telephone,
        statut=driver.statut,
        equipe=driver.equipe,
        profil_vehicule=driver.profil_vehicule,
        interim=driver.interim,
        date_entree=driver.date_entree,
        date_sortie=driver.date_sortie,
        external_id_depantime=driver.external_id_depantime,
        last_sync_at=driver.last_sync_at,
        created_at=driver.created_at,
        updated_at=driver.updated_at,
        required_document_type_ids=doctype_ids,
    )


def _load_requirements(db: Session, driver_ids: list[UUID]) -> dict[UUID, list[UUID]]:
    if not driver_ids:
        return {}
    rows = (
        db.query(DriverRequiredDocument.driver_id, DriverRequiredDocument.document_type_id)
        .filter(DriverRequiredDocument.driver_id.in_(driver_ids))
        .all()
    )
    grouped: dict[UUID, list[UUID]] = defaultdict(list)
    for driver_id, doctype_id in rows:
        grouped[driver_id].append(doctype_id)
    return grouped


@router.get("", response_model=list[DriverOut])
def list_drivers(
    db: Annotated[Session, Depends(get_db)],
    include_archived: bool = False,
):
    q = db.query(Driver)
    if not include_archived:
        q = q.filter(Driver.statut == DriverStatus.ACTIVE.value)
    drivers = q.order_by(Driver.nom, Driver.prenom).all()
    grouped = _load_requirements(db, [d.id for d in drivers])
    return [_serialize(d, grouped.get(d.id, [])) for d in drivers]


@router.get("/{driver_id}", response_model=DriverOut)
def get_driver(driver_id: UUID, db: Annotated[Session, Depends(get_db)]):
    driver = db.get(Driver, driver_id)
    if not driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Depanneur introuvable")
    grouped = _load_requirements(db, [driver.id])
    return _serialize(driver, grouped.get(driver.id, []))
