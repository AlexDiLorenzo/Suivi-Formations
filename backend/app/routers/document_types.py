from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_admin
from app.models import DocumentType
from app.schemas import DocumentTypeOut


router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get("", response_model=list[DocumentTypeOut])
def list_document_types(db: Annotated[Session, Depends(get_db)]):
    return (
        db.query(DocumentType)
        .order_by(DocumentType.display_order, DocumentType.libelle)
        .all()
    )
