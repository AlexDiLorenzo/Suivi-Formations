import hashlib
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_admin
from app.models import (
    AdminUser,
    Document,
    DocumentRequest,
    DocumentType,
    DocumentVersion,
    DocumentVersionStatus,
    Driver,
    DriverRequiredDocument,
    DriverStatus,
    UploadedBy,
)
from app.mailer import send_magic_link_email
from app.routers.documents import MAX_FILE_BYTES, PDF_MAGIC
from app.schemas import (
    DocumentRequestCreate,
    DocumentRequestCreated,
    PublicDocumentRequestInfo,
)
from app.storage import encrypt_and_store


REQUEST_TTL_DAYS = 7


admin_router = APIRouter(dependencies=[Depends(get_current_admin)])
public_router = APIRouter()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _frontend_base(request: Request) -> str:
    origin = request.headers.get("origin")
    if origin:
        return origin.rstrip("/")
    return f"{request.url.scheme}://{request.url.netloc}"


def _resolve_request_or_404(db: Session, token: str) -> DocumentRequest:
    req = (
        db.query(DocumentRequest)
        .filter(DocumentRequest.token_hash == _hash_token(token))
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Lien invalide")
    if req.consumed_at is not None:
        raise HTTPException(status_code=410, detail="Lien deja utilise")
    now = datetime.now(timezone.utc)
    if req.expires_at < now:
        raise HTTPException(status_code=410, detail="Lien expire")
    return req


# ---------------- Admin ----------------


@admin_router.post("", response_model=DocumentRequestCreated, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: DocumentRequestCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
):
    driver = db.get(Driver, payload.driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Depanneur introuvable")
    if driver.statut != DriverStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le depanneur n'est pas actif",
        )
    if not db.get(DocumentType, payload.document_type_id):
        raise HTTPException(status_code=404, detail="Type de document introuvable")

    requirement = (
        db.query(DriverRequiredDocument)
        .filter(
            DriverRequiredDocument.driver_id == payload.driver_id,
            DriverRequiredDocument.document_type_id == payload.document_type_id,
        )
        .first()
    )
    if not requirement:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce type de document n'est pas applicable a ce depanneur",
        )

    doc_type = db.get(DocumentType, payload.document_type_id)

    token = secrets.token_urlsafe(32)
    doc_request = DocumentRequest(
        driver_id=payload.driver_id,
        document_type_id=payload.document_type_id,
        token_hash=_hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=REQUEST_TTL_DAYS),
        created_by_admin_id=current_admin.id,
    )
    db.add(doc_request)
    db.commit()
    db.refresh(doc_request)

    magic_link = f"{_frontend_base(request)}/upload/{token}"

    email_sent = False
    email_error: str | None = None
    if driver.email:
        email_sent, email_error = send_magic_link_email(
            to=driver.email,
            driver_prenom=driver.prenom,
            doc_type_libelle=doc_type.libelle if doc_type else "document",
            magic_link=magic_link,
            expires_at=doc_request.expires_at,
        )
    else:
        email_error = "Le depanneur n'a pas d'email enregistre"

    return DocumentRequestCreated(
        id=doc_request.id,
        token=token,
        magic_link=magic_link,
        expires_at=doc_request.expires_at,
        driver_email=driver.email,
        email_sent=email_sent,
        email_error=email_error,
    )


# ---------------- Public (no auth) ----------------


@public_router.get("/{token}", response_model=PublicDocumentRequestInfo)
def public_get(token: str, db: Annotated[Session, Depends(get_db)]):
    req = _resolve_request_or_404(db, token)
    driver = db.get(Driver, req.driver_id)
    doc_type = db.get(DocumentType, req.document_type_id)
    if not driver or not doc_type:
        raise HTTPException(status_code=404, detail="Lien invalide")
    return PublicDocumentRequestInfo(
        driver_prenom=driver.prenom,
        driver_nom=driver.nom,
        document_type_code=doc_type.code,
        document_type_libelle=doc_type.libelle,
        duree_validite_jours_default=doc_type.duree_validite_jours_default,
        expires_at=req.expires_at,
    )


@public_router.post("/{token}/upload", status_code=status.HTTP_201_CREATED)
async def public_upload(
    token: str,
    db: Annotated[Session, Depends(get_db)],
    date_emission: Annotated[date, Form()],
    date_peremption: Annotated[date, Form()],
    file: Annotated[UploadFile, File()],
):
    req = _resolve_request_or_404(db, token)

    if date_peremption < date_emission:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La date de peremption doit etre posterieure a la date d'emission",
        )
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format invalide : seuls les PDF sont acceptes",
        )

    raw = await file.read()
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Fichier trop volumineux (max {MAX_FILE_BYTES // (1024 * 1024)} MB)",
        )
    if not raw.startswith(PDF_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier ne semble pas etre un vrai PDF (entete invalide)",
        )

    relative_path, sha256, size = encrypt_and_store(raw)

    document = (
        db.query(Document)
        .filter(
            Document.driver_id == req.driver_id,
            Document.document_type_id == req.document_type_id,
        )
        .first()
    )
    if not document:
        document = Document(driver_id=req.driver_id, document_type_id=req.document_type_id)
        db.add(document)
        db.flush()

    version = DocumentVersion(
        document_id=document.id,
        file_path_encrypted=relative_path,
        file_sha256=sha256,
        file_size_bytes=size,
        original_filename=file.filename or "document.pdf",
        mime_type="application/pdf",
        date_emission=date_emission,
        date_peremption=date_peremption,
        uploaded_by=UploadedBy.DRIVER.value,
        statut=DocumentVersionStatus.PENDING.value,
    )
    db.add(version)
    req.consumed_at = datetime.now(timezone.utc)
    db.commit()

    return {"status": "ok"}
