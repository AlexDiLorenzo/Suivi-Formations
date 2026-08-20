"""Consultation des depanneurs et reglage de ce qu'on exige d'eux.

La liste elle-meme n'est pas modifiable ici : elle est le reflet de l'equipe du
depannage tenue dans DepanTime (cf. app/sync_depantime.py). Ni creation, ni
archivage, ni modification de l'identite — tout cela serait ecrase a la
synchronisation suivante et ferait diverger les deux outils. Ne restent
modifiables que le profil de permis et l'applicabilite des documents, qui
n'existent que dans cette application.
"""
from collections import defaultdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_admin
from app.models import (
    DocumentType,
    Driver,
    DriverProfil,
    DriverRequiredDocument,
    DriverStatus,
)
from app.schemas import DriverOut, DriverUpdate, RequirementsSync
from app.socle import ids_du_socle


router = APIRouter(dependencies=[Depends(get_current_admin)])


def _serialize(driver: Driver, doctype_ids: list[UUID]) -> DriverOut:
    return DriverOut(
        id=driver.id,
        prenom=driver.prenom,
        nom=driver.nom,
        email=driver.email,
        telephone=driver.telephone,
        statut=driver.statut,
        profil=driver.profil,
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


@router.patch("/{driver_id}", response_model=DriverOut)
def update_driver(driver_id: UUID, payload: DriverUpdate, db: Annotated[Session, Depends(get_db)]):
    """Modifie le profil de permis, et rien d'autre (cf. DriverUpdate)."""
    driver = db.get(Driver, driver_id)
    if not driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Depanneur introuvable")
    donnees = payload.model_dump(exclude_unset=True)
    profil = donnees.get("profil")
    if profil is not None and profil not in {p.value for p in DriverProfil}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Profil inconnu"
        )
    for k, v in donnees.items():
        setattr(driver, k, v)
    db.commit()
    db.refresh(driver)
    grouped = _load_requirements(db, [driver.id])
    return _serialize(driver, grouped.get(driver.id, []))


@router.put("/{driver_id}/requirements", response_model=DriverOut)
def sync_requirements(
    driver_id: UUID,
    payload: RequirementsSync,
    db: Annotated[Session, Depends(get_db)],
):
    driver = db.get(Driver, driver_id)
    if not driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Depanneur introuvable")

    target = set(payload.document_type_ids)
    if target:
        valid_count = (
            db.query(DocumentType).filter(DocumentType.id.in_(target)).count()
        )
        if valid_count != len(target):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Au moins un type de document est inconnu",
            )

    # Le socle s'impose : seules les habilitations se cochent. On le reajoute
    # ici quoi qu'envoie le client — sans quoi un decochage passerait, pour
    # etre defait a la synchro suivante, ce qui serait incomprehensible.
    target |= ids_du_socle(db)

    existing = (
        db.query(DriverRequiredDocument)
        .filter(DriverRequiredDocument.driver_id == driver_id)
        .all()
    )
    existing_ids = {r.document_type_id for r in existing}

    for r in existing:
        if r.document_type_id not in target:
            db.delete(r)

    for new_id in target - existing_ids:
        db.add(DriverRequiredDocument(driver_id=driver_id, document_type_id=new_id))

    db.commit()
    db.refresh(driver)
    grouped = _load_requirements(db, [driver.id])
    return _serialize(driver, grouped.get(driver.id, []))
