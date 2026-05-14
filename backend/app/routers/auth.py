import base64
import io
from typing import Annotated

import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_admin
from app.models import AdminUser
from app.schemas import (
    LoginRequest,
    MeResponse,
    TokenResponse,
    TotpEnableRequest,
    TotpSetupResponse,
)
from app.security import (
    create_access_token,
    generate_totp_secret,
    totp_provisioning_uri,
    verify_password,
    verify_totp,
)


router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]):
    admin = db.query(AdminUser).filter(AdminUser.email == payload.email.lower()).first()
    if not admin or not admin.is_active or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Identifiants invalides")
    if admin.totp_enabled:
        if not payload.totp_code:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Code 2FA requis")
        if not verify_totp(admin.totp_secret or "", payload.totp_code):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Code 2FA invalide")
    return TokenResponse(access_token=create_access_token(str(admin.id)))


@router.get("/me", response_model=MeResponse)
def me(current: Annotated[AdminUser, Depends(get_current_admin)]):
    return current


@router.post("/totp/setup", response_model=TotpSetupResponse)
def totp_setup(
    current: Annotated[AdminUser, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    if current.totp_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="2FA deja active")
    secret = generate_totp_secret()
    current.totp_secret = secret
    db.commit()
    uri = totp_provisioning_uri(secret, current.email)
    buf = io.BytesIO()
    qrcode.make(uri).save(buf, format="PNG")
    return TotpSetupResponse(
        secret=secret,
        provisioning_uri=uri,
        qr_code_data_uri="data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(),
    )


@router.post("/totp/enable")
def totp_enable(
    payload: TotpEnableRequest,
    current: Annotated[AdminUser, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    if current.totp_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="2FA deja active")
    if not current.totp_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pas de setup en cours, appeler /totp/setup d'abord")
    if not verify_totp(current.totp_secret, payload.totp_code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Code invalide")
    current.totp_enabled = True
    db.commit()
    return {"status": "enabled"}
