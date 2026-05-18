import logging
from datetime import date, datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import docusign as ds
from app.config import get_settings
from app.db import get_db
from app.deps import get_current_admin
from app.models import (
    SIGNATURE_TERMINAL_STATUSES,
    AdminUser,
    Document,
    DocumentModeAcquisition,
    DocumentType,
    DocumentVersion,
    DocumentVersionStatus,
    Driver,
    DriverRequiredDocument,
    SignatureEnvelope,
    SignatureEnvelopeStatus,
    UploadedBy,
)
from app.schemas import DocusignSendRequest, SignatureEnvelopeOut
from app.storage import encrypt_and_store


router = APIRouter(dependencies=[Depends(get_current_admin)])
logger = logging.getLogger(__name__)

# Filet de securite si le type de document n'a pas de duree configuree.
ATTESTATION_DEFAULT_VALIDITE_JOURS = 90


def _ensure_enabled() -> None:
    if not get_settings().docusign_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="L'integration DocuSign n'est pas configuree "
                   "(variables d'environnement DOCUSIGN_* manquantes).",
        )


def _latest_envelope(
    db: Session, driver_id: UUID, document_type_id: UUID
) -> SignatureEnvelope | None:
    return (
        db.query(SignatureEnvelope)
        .filter(
            SignatureEnvelope.driver_id == driver_id,
            SignatureEnvelope.document_type_id == document_type_id,
        )
        .order_by(SignatureEnvelope.created_at.desc())
        .first()
    )


@router.get("/envelope", response_model=SignatureEnvelopeOut | None)
def get_latest_envelope(
    driver_id: UUID,
    document_type_id: UUID,
    db: Annotated[Session, Depends(get_db)],
):
    """Derniere enveloppe pour un couple (depanneur, type), ou null s'il n'y en a pas."""
    return _latest_envelope(db, driver_id, document_type_id)


@router.post("/send", response_model=SignatureEnvelopeOut, status_code=status.HTTP_201_CREATED)
def send_for_signature(
    payload: DocusignSendRequest,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
):
    _ensure_enabled()

    driver = db.get(Driver, payload.driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Depanneur introuvable")
    if not driver.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce depanneur n'a pas d'email : impossible d'envoyer une signature DocuSign.",
        )

    doc_type = db.get(DocumentType, payload.document_type_id)
    if not doc_type:
        raise HTTPException(status_code=404, detail="Type de document introuvable")
    if doc_type.mode_acquisition != DocumentModeAcquisition.DOCUSIGN.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Le type {doc_type.code} ne se signe pas via DocuSign.",
        )

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
            detail=f"Le type {doc_type.code} n'est pas applicable a ce depanneur. "
                   "Coche-le d'abord dans la fiche depanneur.",
        )

    existing = _latest_envelope(db, payload.driver_id, payload.document_type_id)
    if existing and existing.status not in SIGNATURE_TERMINAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une signature est deja en cours pour ce document. "
                   "Rafraichis son statut ou attends sa fin avant d'en relancer une.",
        )

    recipient_name = f"{driver.prenom} {driver.nom}".strip()
    subject = f"Attestation sur l'honneur — {doc_type.libelle} ({payload.mois} {payload.annee})"
    try:
        result = ds.create_envelope(
            recipient_name=recipient_name,
            recipient_email=driver.email,
            mois=payload.mois,
            annee=payload.annee,
            email_subject=subject,
        )
    except ds.DocusignError as exc:
        logger.warning("Envoi DocuSign refuse : %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except Exception as exc:  # httpx injoignable, cle RSA invalide, reponse inattendue...
        logger.exception("Echec inattendu de l'envoi DocuSign")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Erreur DocuSign inattendue ({type(exc).__name__}) : {exc}",
        )

    envelope = SignatureEnvelope(
        driver_id=payload.driver_id,
        document_type_id=payload.document_type_id,
        envelope_id=result["envelopeId"],
        status=result.get("status", SignatureEnvelopeStatus.SENT.value),
        mois=payload.mois,
        annee=payload.annee,
        recipient_email=driver.email,
        created_by_admin_id=current_admin.id,
    )
    db.add(envelope)
    db.commit()
    db.refresh(envelope)
    return envelope


@router.post("/envelopes/{envelope_db_id}/refresh", response_model=SignatureEnvelopeOut)
def refresh_envelope(
    envelope_db_id: UUID,
    db: Annotated[Session, Depends(get_db)],
):
    """Interroge DocuSign ; si l'enveloppe est signee, importe le PDF en version validee."""
    _ensure_enabled()
    envelope = db.get(SignatureEnvelope, envelope_db_id)
    if not envelope:
        raise HTTPException(status_code=404, detail="Enveloppe introuvable")

    # Deja completee et importee : rien a refaire (pas de double import).
    if envelope.imported_version_id is not None:
        return envelope

    try:
        ds_status = ds.get_envelope_status(envelope.envelope_id)
    except ds.DocusignError as exc:
        logger.warning("Rafraichissement DocuSign refuse : %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except Exception as exc:
        logger.exception("Echec inattendu du rafraichissement DocuSign")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Erreur DocuSign inattendue ({type(exc).__name__}) : {exc}",
        )

    if ds_status:
        envelope.status = ds_status

    if ds_status == SignatureEnvelopeStatus.COMPLETED.value:
        _import_signed_document(db, envelope)

    db.commit()
    db.refresh(envelope)
    return envelope


def _import_signed_document(db: Session, envelope: SignatureEnvelope) -> None:
    """Telecharge le PDF signe et cree une DocumentVersion validee.

    L'invariant "pas d'ecrasement" est respecte : on ajoute une nouvelle
    version, on ne touche pas aux precedentes.
    """
    try:
        pdf_bytes = ds.download_combined_pdf(envelope.envelope_id)
    except ds.DocusignError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    relative_path, sha256, size = encrypt_and_store(pdf_bytes)

    doc_type = db.get(DocumentType, envelope.document_type_id)
    document = (
        db.query(Document)
        .filter(
            Document.driver_id == envelope.driver_id,
            Document.document_type_id == envelope.document_type_id,
        )
        .first()
    )
    if not document:
        document = Document(
            driver_id=envelope.driver_id,
            document_type_id=envelope.document_type_id,
        )
        db.add(document)
        db.flush()

    today = date.today()
    perimable = doc_type is None or doc_type.est_perimable
    validite = (doc_type.duree_validite_jours_default if doc_type else None) or ATTESTATION_DEFAULT_VALIDITE_JOURS
    date_peremption = today + timedelta(days=validite) if perimable else None

    now = datetime.now(timezone.utc)
    version = DocumentVersion(
        document_id=document.id,
        file_path_encrypted=relative_path,
        file_sha256=sha256,
        file_size_bytes=size,
        original_filename=f"attestation_{envelope.mois}_{envelope.annee}_signee.pdf",
        mime_type="application/pdf",
        date_emission=today,
        date_peremption=date_peremption,
        uploaded_by=UploadedBy.DOCUSIGN.value,
        statut=DocumentVersionStatus.VALIDATED.value,
        validated_by_admin_id=envelope.created_by_admin_id,
        validated_at=now,
    )
    db.add(version)
    db.flush()

    document.current_version_id = version.id
    envelope.imported_version_id = version.id
    envelope.completed_at = now
