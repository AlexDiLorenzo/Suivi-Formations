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


class DriverUpdate(BaseModel):
    prenom: str | None = None
    nom: str | None = None
    email: EmailStr | None = None
    telephone: str | None = None
    date_entree: date | None = None
    date_sortie: date | None = None
    external_id_depantime: str | None = None


class DriverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    prenom: str
    nom: str
    email: EmailStr | None
    telephone: str | None
    statut: str
    date_entree: date | None
    date_sortie: date | None
    external_id_depantime: str | None
    last_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DocumentTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    libelle: str
    duree_validite_jours_default: int | None
    display_order: int


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
