from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    full_name: str
    totp_enabled: bool


class TotpSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    qr_code_data_uri: str


class TotpEnableRequest(BaseModel):
    totp_code: str = Field(min_length=6, max_length=10)


class DriverCreate(BaseModel):
    prenom: str
    nom: str
    email: EmailStr | None = None
    telephone: str | None = None
    date_entree: date | None = None
    external_id_depantime: str | None = None
    profil: str | None = None


class DriverUpdate(BaseModel):
    prenom: str | None = None
    nom: str | None = None
    email: EmailStr | None = None
    telephone: str | None = None
    date_entree: date | None = None
    date_sortie: date | None = None
    external_id_depantime: str | None = None
    profil: str | None = None


class DriverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    prenom: str
    nom: str
    email: EmailStr | None
    telephone: str | None
    statut: str
    profil: str | None
    date_entree: date | None
    date_sortie: date | None
    external_id_depantime: str | None
    last_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime
    required_document_type_ids: list[UUID] = Field(default_factory=list)


class RequirementsSync(BaseModel):
    document_type_ids: list[UUID]


class DocumentTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    libelle: str
    duree_validite_jours_default: int | None
    categorie: str | None
    est_perimable: bool
    criticite: str
    mode_acquisition: str
    display_order: int


class ProfilOut(BaseModel):
    value: str
    label: str
    document_codes: list[str]


class RequirementCreate(BaseModel):
    driver_id: UUID
    document_type_id: UUID


class RequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    driver_id: UUID
    document_type_id: UUID
    required_since: date
    created_at: datetime


class CellStatus(str, Enum):
    GREEN = "green"
    ORANGE = "orange"
    RED = "red"
    GREY = "grey"


class CellRedReason(str, Enum):
    EXPIRED = "expired"
    NEVER_RECEIVED = "never_received"


class DashboardCell(BaseModel):
    document_type_id: UUID
    status: CellStatus
    reason: CellRedReason | None = None
    date_peremption: date | None = None
    days_until_expiry: int | None = None
    current_version_id: UUID | None = None
    has_pending_version: bool = False
    pending_version_id: UUID | None = None
    open_request_sent_at: datetime | None = None


class DashboardDriver(BaseModel):
    id: UUID
    prenom: str
    nom: str
    statut: str
    cells: list[DashboardCell]


class DashboardDocType(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    libelle: str
    display_order: int


class DashboardSummary(BaseModel):
    by_status: dict[CellStatus, int]


class DashboardResponse(BaseModel):
    doc_types: list[DashboardDocType]
    drivers: list[DashboardDriver]
    summary: DashboardSummary


class DocumentVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_id: UUID
    original_filename: str
    mime_type: str
    file_size_bytes: int
    date_emission: date
    date_peremption: date
    uploaded_by: str
    uploaded_at: datetime
    statut: str
    rejection_reason: str | None = None
    validated_at: datetime | None = None


class RejectionRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class DocumentRequestCreate(BaseModel):
    driver_id: UUID
    document_type_id: UUID


class DocumentRequestCreated(BaseModel):
    id: UUID
    token: str
    magic_link: str
    expires_at: datetime
    driver_email: EmailStr | None = None
    email_sent: bool = False
    email_error: str | None = None


class BulkDocumentRequestCreate(BaseModel):
    driver_id: UUID


class BulkRequestItem(BaseModel):
    document_type_id: UUID
    document_type_code: str
    document_type_libelle: str
    magic_link: str


class BulkDocumentRequestResult(BaseModel):
    count: int
    driver_email: EmailStr | None = None
    email_sent: bool = False
    email_error: str | None = None
    items: list[BulkRequestItem]


class PublicDocumentRequestInfo(BaseModel):
    driver_prenom: str
    driver_nom: str
    document_type_code: str
    document_type_libelle: str
    duree_validite_jours_default: int | None
    expires_at: datetime


class DueReminderItem(BaseModel):
    reminder_id: UUID
    type: str
    driver_email: EmailStr
    driver_prenom: str
    driver_nom: str
    document_type_code: str
    document_type_libelle: str
    days_until_expiry: int | None
    date_peremption: date | None
    magic_link: str
    magic_link_expires_at: datetime


class MarkSentRequest(BaseModel):
    reminder_ids: list[UUID]


class SkippedReminderItem(BaseModel):
    driver_id: UUID
    driver_nom: str
    document_type_code: str
    type: str
    reason: str


class DueRemindersResponse(BaseModel):
    items: list[DueReminderItem]
    skipped: list[SkippedReminderItem]
