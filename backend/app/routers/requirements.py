from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_admin
from app.models import DocumentType, Driver, DriverRequiredDocument
from app.schemas import RequirementCreate, RequirementOut


router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get("/driver/{driver_id}", response_model=list[RequirementOut])
def list_for_driver(driver_id: UUID, db: Annotated[Session, Depends(get_db)]):
    return (
        db.query(DriverRequiredDocument)
        .filter(DriverRequiredDocument.driver_id == driver_id)
        .all()
    )


@router.post("", response_model=RequirementOut, status_code=status.HTTP_201_CREATED)
def add_requirement(payload: RequirementCreate, db: Annotated[Session, Depends(get_db)]):
    if not db.get(Driver, payload.driver_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Depanneur introuvable")
    if not db.get(DocumentType, payload.document_type_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Type de document introuvable")
    existing = (
        db.query(DriverRequiredDocument)
        .filter(
            DriverRequiredDocument.driver_id == payload.driver_id,
            DriverRequiredDocument.document_type_id == payload.document_type_id,
        )
        .first()
    )
    if existing:
        return existing
    req = DriverRequiredDocument(
        driver_id=payload.driver_id,
        document_type_id=payload.document_type_id,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.delete("/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_requirement(requirement_id: UUID, db: Annotated[Session, Depends(get_db)]):
    req = db.get(DriverRequiredDocument, requirement_id)
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exigence introuvable")
    db.delete(req)
    db.commit()
