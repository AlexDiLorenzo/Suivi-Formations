from datetime import date, datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_admin
from app.models import (
    AdminUser,
    Document,
    DocumentType,
    DocumentVersion,
    DocumentVersionStatus,
    Driver,
    DriverRequiredDocument,
    UploadedBy,
)
from app.schemas import DocumentVersionOut, RejectionRequest
from app.storage import StorageError, decrypt_and_read, encrypt_and_store


MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
PDF_MAGIC = b"%PDF-"


router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.post("/upload", response_model=DocumentVersionOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    driver_id: Annotated[UUID, Form()],
    document_type_id: Annotated[UUID, Form()],
    date_emission: Annotated[date, Form()],
    date_peremption: Annotated[date, Form()],
    file: Annotated[UploadFile, File()],
):
    if date_peremption < date_emission:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La date de peremption doit etre posterieure a la date d'emission",
        )

    driver = db.get(Driver, driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Depanneur introuvable")
    doc_type = db.get(DocumentType, document_type_id)
    if not doc_type:
        raise HTTPException(status_code=404, detail="Type de document introuvable")

    requirement = (
        db.query(DriverRequiredDocument)
        .filter(
            DriverRequiredDocument.driver_id == driver_id,
            DriverRequiredDocument.document_type_id == document_type_id,
        )
        .first()
    )
    if not requirement:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Le type {doc_type.code} n'est pas applicable a ce depanneur. "
                   "Coche-le d'abord dans la fiche depanneur.",
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
        .filter(Document.driver_id == driver_id, Document.document_type_id == document_type_id)
        .first()
    )
    if not document:
        document = Document(driver_id=driver_id, document_type_id=document_type_id)
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
        uploaded_by=UploadedBy.ADMIN.value,
        uploaded_by_admin_id=current_admin.id,
        statut=DocumentVersionStatus.VALIDATED.value,
        validated_by_admin_id=current_admin.id,
        validated_at=datetime.now(timezone.utc),
    )
    db.add(version)
    db.flush()

    document.current_version_id = version.id
    db.commit()
    db.refresh(version)
    return version


@router.get("/{version_id}", response_model=DocumentVersionOut)
def get_version(version_id: UUID, db: Annotated[Session, Depends(get_db)]):
    version = db.get(DocumentVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version introuvable")
    return version


@router.get("/{version_id}/download")
def download_document(version_id: UUID, db: Annotated[Session, Depends(get_db)]):
    version = db.get(DocumentVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version introuvable")
    try:
        plaintext = decrypt_and_read(version.file_path_encrypted)
    except StorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    safe_name = version.original_filename.replace('"', "_")
    return Response(
        content=plaintext,
        media_type=version.mime_type,
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )


@router.post("/{version_id}/validate", response_model=DocumentVersionOut)
def validate_version(
    version_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
):
    version = db.get(DocumentVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version introuvable")
    if version.statut != DocumentVersionStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cette version n'est pas en attente (statut actuel : {version.statut})",
        )
    document = db.get(Document, version.document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document parent introuvable")

    version.statut = DocumentVersionStatus.VALIDATED.value
    version.validated_by_admin_id = current_admin.id
    version.validated_at = datetime.now(timezone.utc)
    document.current_version_id = version.id
    db.commit()
    db.refresh(version)
    return version


@router.post("/{version_id}/reject", response_model=DocumentVersionOut)
def reject_version(
    version_id: UUID,
    payload: RejectionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
):
    version = db.get(DocumentVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version introuvable")
    if version.statut != DocumentVersionStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cette version n'est pas en attente (statut actuel : {version.statut})",
        )
    version.statut = DocumentVersionStatus.REJECTED.value
    version.validated_by_admin_id = current_admin.id
    version.validated_at = datetime.now(timezone.utc)
    version.rejection_reason = payload.reason
    db.commit()
    db.refresh(version)
    return version
