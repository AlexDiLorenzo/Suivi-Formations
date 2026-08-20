"""Liste des types de documents.

Lecture seule : le niveau d'exigence (socle / habilitation / complementaire)
est **impose par le code** — il est pose par `scripts/seed_doctypes.py` et
n'est pas reglable depuis l'application. Un reglage par ecran donnerait
l'illusion d'un parametrage alors que le socle doit rester le meme pour tout
le monde.
"""
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
