from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_admin
from app.models import Driver, DriverStatus
from app.schemas import DriverCreate, DriverOut, DriverUpdate


router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get("", response_model=list[DriverOut])
def list_drivers(
    db: Annotated[Session, Depends(get_db)],
    include_archived: bool = False,
):
    q = db.query(Driver)
    if not include_archived:
        q = q.filter(Driver.statut == DriverStatus.ACTIVE.value)
    return q.order_by(Driver.nom, Driver.prenom).all()


@router.post("", response_model=DriverOut, status_code=status.HTTP_201_CREATED)
def create_driver(payload: DriverCreate, db: Annotated[Session, Depends(get_db)]):
    driver = Driver(**payload.model_dump(exclude_unset=True))
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return driver


@router.get("/{driver_id}", response_model=DriverOut)
def get_driver(driver_id: UUID, db: Annotated[Session, Depends(get_db)]):
    driver = db.get(Driver, driver_id)
    if not driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Depanneur introuvable")
    return driver


@router.patch("/{driver_id}", response_model=DriverOut)
def update_driver(driver_id: UUID, payload: DriverUpdate, db: Annotated[Session, Depends(get_db)]):
    driver = db.get(Driver, driver_id)
    if not driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Depanneur introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(driver, k, v)
    db.commit()
    db.refresh(driver)
    return driver


@router.post("/{driver_id}/archive", response_model=DriverOut)
def archive_driver(driver_id: UUID, db: Annotated[Session, Depends(get_db)]):
    driver = db.get(Driver, driver_id)
    if not driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Depanneur introuvable")
    driver.statut = DriverStatus.ARCHIVED.value
    if not driver.date_sortie:
        driver.date_sortie = date.today()
    db.commit()
    db.refresh(driver)
    return driver
