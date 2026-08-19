from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_admin
from app.models import DocumentNiveauExigence, DocumentType
from app.schemas import DocumentTypeOut, DocumentTypeUpdate


router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get("", response_model=list[DocumentTypeOut])
def list_document_types(db: Annotated[Session, Depends(get_db)]):
    return (
        db.query(DocumentType)
        .order_by(DocumentType.display_order, DocumentType.libelle)
        .all()
    )


@router.patch("/{type_id}", response_model=DocumentTypeOut)
def update_document_type(
    type_id: UUID,
    payload: DocumentTypeUpdate,
    db: Annotated[Session, Depends(get_db)],
):
    """Reglage du niveau d'exigence depuis l'application.

    La liste des documents attendus n'est pas figee : l'admin doit pouvoir
    basculer un type entre socle obligatoire, selon profil et complementaire
    sans passer par un reseed.
    """
    doc_type = db.get(DocumentType, type_id)
    if not doc_type:
        raise HTTPException(status_code=404, detail="Type de document introuvable")

    data = payload.model_dump(exclude_unset=True)
    niveau = data.get("niveau_exigence")
    if niveau is not None and niveau not in {n.value for n in DocumentNiveauExigence}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Niveau d'exigence inconnu",
        )
    for key, value in data.items():
        setattr(doc_type, key, value)
    db.commit()
    db.refresh(doc_type)
    return doc_type
