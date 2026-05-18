"""Integration DocuSign : authentification JWT Grant + gestion des enveloppes.

Etape 10e : signature de l'attestation sur l'honneur de validite du permis.
Implemente avec httpx + python-jose (deja presents) plutot que le SDK
docusign-esign, pour garder un nombre de dependances minimal.
"""
import time

import httpx
from jose import jwt

from app.config import get_settings


class DocusignError(RuntimeError):
    """Erreur fonctionnelle DocuSign : le message est destine a l'admin."""


_JWT_LIFETIME_SEC = 3600
_TOKEN_SAFETY_MARGIN_SEC = 300

# Cache process-wide : le token JWT vaut 1h, le base_uri du compte ne change pas.
_cached_token: str | None = None
_token_expiry: float = 0.0
_cached_base_uri: str | None = None


def _oauth_host() -> str:
    return get_settings().docusign_oauth_host


def consent_url() -> str:
    """URL a ouvrir une fois pour autoriser l'application (consentement admin)."""
    key = get_settings().docusign_integration_key
    return (
        f"https://{_oauth_host()}/oauth/auth?response_type=code"
        f"&scope=signature+impersonation&client_id={key}"
        "&redirect_uri=https://developers.docusign.com/platform/auth/consent"
    )


def _request_access_token() -> str:
    settings = get_settings()
    now = int(time.time())
    assertion = jwt.encode(
        {
            "iss": settings.docusign_integration_key,
            "sub": settings.docusign_user_id,
            "aud": _oauth_host(),
            "iat": now,
            "exp": now + _JWT_LIFETIME_SEC,
            "scope": "signature impersonation",
        },
        settings.docusign_private_key_pem,
        algorithm="RS256",
    )
    resp = httpx.post(
        f"https://{_oauth_host()}/oauth/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        },
        timeout=20.0,
    )
    if resp.status_code != 200:
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if body.get("error") == "consent_required":
            raise DocusignError(
                "Consentement DocuSign requis : ouvre une fois cette URL avec le "
                f"compte administrateur DocuSign puis accepte — {consent_url()}"
            )
        raise DocusignError(
            f"Echec d'authentification DocuSign ({resp.status_code}) : {resp.text}"
        )
    return resp.json()["access_token"]


def _get_access_token() -> str:
    global _cached_token, _token_expiry
    if _cached_token and time.time() < _token_expiry:
        return _cached_token
    _cached_token = _request_access_token()
    _token_expiry = time.time() + _JWT_LIFETIME_SEC - _TOKEN_SAFETY_MARGIN_SEC
    return _cached_token


def _get_base_uri(token: str) -> str:
    """Resout le base_uri du compte (na1/na2/eu...) via /oauth/userinfo."""
    global _cached_base_uri
    if _cached_base_uri:
        return _cached_base_uri
    settings = get_settings()
    resp = httpx.get(
        f"https://{_oauth_host()}/oauth/userinfo",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20.0,
    )
    if resp.status_code != 200:
        raise DocusignError(
            f"Impossible de recuperer le compte DocuSign ({resp.status_code})"
        )
    for account in resp.json().get("accounts", []):
        if account.get("account_id") == settings.docusign_account_id:
            _cached_base_uri = account["base_uri"]
            return _cached_base_uri
    raise DocusignError(
        f"Le compte DocuSign {settings.docusign_account_id} est introuvable "
        "pour cet utilisateur (verifie DOCUSIGN_ACCOUNT_ID)."
    )


def _api_base(token: str) -> str:
    settings = get_settings()
    return f"{_get_base_uri(token)}/restapi/v2.1/accounts/{settings.docusign_account_id}"


def create_envelope(
    *,
    recipient_name: str,
    recipient_email: str,
    mois: str,
    annee: int,
    email_subject: str,
) -> dict:
    """Cree et envoie une enveloppe depuis le template de l'attestation.

    Renvoie le JSON DocuSign ({envelopeId, status, ...}).
    """
    settings = get_settings()
    token = _get_access_token()
    annee_str = str(annee)
    body = {
        "templateId": settings.docusign_template_id,
        "status": "sent",
        "templateRoles": [
            {
                "roleName": settings.docusign_role_name,
                "name": recipient_name,
                "email": recipient_email,
                # Les textTabs pre-remplissent le document ; les customFields
                # servent au classement de l'enveloppe cote DocuSign.
                "tabs": {
                    "textTabs": [
                        {"tabLabel": "mois", "value": mois},
                        {"tabLabel": "annee", "value": annee_str},
                    ]
                },
            }
        ],
        "customFields": {
            "textCustomFields": [
                {"name": "Mois", "value": mois},
                {"name": "Année", "value": annee_str},
            ]
        },
        "emailSubject": email_subject,
    }
    resp = httpx.post(
        f"{_api_base(token)}/envelopes",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
        timeout=30.0,
    )
    if resp.status_code not in (200, 201):
        raise DocusignError(
            f"Echec de creation de l'enveloppe DocuSign ({resp.status_code}) : {resp.text}"
        )
    return resp.json()


def get_envelope_status(envelope_id: str) -> str:
    token = _get_access_token()
    resp = httpx.get(
        f"{_api_base(token)}/envelopes/{envelope_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20.0,
    )
    if resp.status_code != 200:
        raise DocusignError(
            f"Statut DocuSign indisponible ({resp.status_code}) : {resp.text}"
        )
    return resp.json().get("status", "")


def download_combined_pdf(envelope_id: str) -> bytes:
    """Telecharge le PDF combine (document + page de certificat) de l'enveloppe."""
    token = _get_access_token()
    resp = httpx.get(
        f"{_api_base(token)}/envelopes/{envelope_id}/documents/combined",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/pdf"},
        timeout=60.0,
    )
    if resp.status_code != 200:
        raise DocusignError(
            f"Telechargement du PDF signe impossible ({resp.status_code})"
        )
    return resp.content
