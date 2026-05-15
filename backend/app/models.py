import uuid
from datetime import datetime, date
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class DriverStatus(str, PyEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class DocumentVersionStatus(str, PyEnum):
    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"


class UploadedBy(str, PyEnum):
    ADMIN = "admin"
    DRIVER = "driver"


class DriverProfil(str, PyEnum):
    PERMIS_B = "permis_b"
    PERMIS_C_CE = "permis_c_ce"


class DocumentCategorie(str, PyEnum):
    PERMIS_CONDUITE = "permis_conduite"
    CACES_AUTORISATIONS = "caces_autorisations"
    FORMATIONS_INTERNES = "formations_internes"
    DIPLOMES = "diplomes"
    ADMINISTRATIF = "administratif"


class DocumentCriticite(str, PyEnum):
    CRITIQUE = "critique"
    STANDARD = "standard"


class DocumentModeAcquisition(str, PyEnum):
    UPLOAD = "upload"
    DOCUSIGN = "docusign"


def _uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[uuid.UUID] = _uuid_pk()
    external_id_depantime: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    prenom: Mapped[str] = mapped_column(String(120), nullable=False)
    nom: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    statut: Mapped[str] = mapped_column(String(20), nullable=False, default=DriverStatus.ACTIVE.value)
    profil: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_entree: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_sortie: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    required_documents: Mapped[list["DriverRequiredDocument"]] = relationship(
        back_populates="driver", cascade="all, delete-orphan"
    )


class DocumentType(Base):
    __tablename__ = "document_types"

    id: Mapped[uuid.UUID] = _uuid_pk()
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    libelle: Mapped[str] = mapped_column(String(120), nullable=False)
    duree_validite_jours_default: Mapped[int | None] = mapped_column(Integer, nullable=True)
    categorie: Mapped[str | None] = mapped_column(String(40), nullable=True)
    est_perimable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criticite: Mapped[str] = mapped_column(String(20), nullable=False, default=DocumentCriticite.STANDARD.value)
    mode_acquisition: Mapped[str] = mapped_column(String(20), nullable=False, default=DocumentModeAcquisition.UPLOAD.value)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DriverRequiredDocument(Base):
    __tablename__ = "driver_required_documents"
    __table_args__ = (UniqueConstraint("driver_id", "document_type_id", name="uq_driver_doctype"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False)
    document_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_types.id", ondelete="RESTRICT"), nullable=False)
    required_since: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    driver: Mapped["Driver"] = relationship(back_populates="required_documents")
    document_type: Mapped["DocumentType"] = relationship()


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("driver_id", "document_type_id", name="uq_doc_driver_type"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False)
    document_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_types.id", ondelete="RESTRICT"), nullable=False)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="SET NULL", use_alter=True, name="fk_doc_current_version"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    date_emission: Mapped[date] = mapped_column(Date, nullable=False)
    date_peremption: Mapped[date | None] = mapped_column(Date, nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(20), nullable=False)
    uploaded_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    statut: Mapped[str] = mapped_column(String(20), nullable=False, default=DocumentVersionStatus.PENDING.value)
    validated_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class DocumentRequest(Base):
    __tablename__ = "document_requests"

    id: Mapped[uuid.UUID] = _uuid_pk()
    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False)
    document_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_types.id", ondelete="RESTRICT"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[uuid.UUID] = _uuid_pk()
    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False, index=True)
    document_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_types.id", ondelete="RESTRICT"), nullable=False)
    document_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="email")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = _uuid_pk()
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
