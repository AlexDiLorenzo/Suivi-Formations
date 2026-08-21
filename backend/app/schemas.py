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


class DriverOut(BaseModel):
    """Une fiche depanneur — en lecture seule, sans exception.

    Tout ce qui est ici appartient a DepanTime (ou a Flotte pour Perols) et est
    reecrit a chaque synchronisation : identite, statut, equipe, type de
    vehicule, interim. L'applicabilite des documents en decoule (cf. app/socle.py)
    au lieu de se cocher. Cette application ne detient que les documents.
    """

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    prenom: str | None
    nom: str
    email: EmailStr | None
    telephone: str | None
    statut: str
    equipe: str | None
    profil_vehicule: str | None
    interim: bool
    date_entree: date | None
    date_sortie: date | None
    external_id_depantime: str | None
    last_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime
    required_document_type_ids: list[UUID] = Field(default_factory=list)


class DocumentTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    libelle: str
    duree_validite_jours_default: int | None
    categorie: str | None
    est_perimable: bool
    niveau_exigence: str
    perimetre: str
    mode_acquisition: str
    display_order: int


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
    signature_status: str | None = None


class DashboardDriver(BaseModel):
    """`score` = conformite au socle applicable, en %. C'est le « il roule ou
    pas ». La qualification se lit en fraction, jamais en % : un complementaire
    absent n'est pas un manquement, l'afficher comme une note le ferait croire.
    """

    id: UUID
    prenom: str | None = None
    nom: str
    statut: str
    email: str | None = None
    equipe: str | None = None
    profil_vehicule: str | None = None
    interim: bool = False
    cells: list[DashboardCell]
    score: int | None = None
    socle_manquants: int = 0
    socle_total: int = 0
    qualification_acquises: int = 0
    qualification_total: int = 0


class DashboardDocType(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    libelle: str
    categorie: str | None = None
    niveau_exigence: str
    perimetre: str
    est_perimable: bool
    duree_validite_jours_default: int | None = None
    display_order: int


class DashboardSummary(BaseModel):
    by_status: dict[CellStatus, int]
    score_global: int | None = None
    qualification_acquises: int = 0
    qualification_total: int = 0


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
    date_peremption: date | None = None
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
    est_perimable: bool
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


class SyncResultOut(BaseModel):
    crees: int
    mis_a_jour: int
    archives: int
    reactives: int
    supprimes: int = 0
    exigences_posees: int = 0
    exigences_retirees: int = 0
    ignores: list[str] = Field(default_factory=list)
    hors_depantime: list[str] = Field(default_factory=list)


class DocusignSendRequest(BaseModel):
    driver_id: UUID
    document_type_id: UUID
    mois: str = Field(min_length=1, max_length=20)
    annee: int = Field(ge=2000, le=2100)


class SignatureEnvelopeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    driver_id: UUID
    document_type_id: UUID
    envelope_id: str
    status: str
    mois: str
    annee: int
    recipient_email: str
    imported_version_id: UUID | None = None
    created_at: datetime
    completed_at: datetime | None = None
