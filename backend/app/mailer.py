"""Envoi d'emails transactionnels via Resend (https://resend.com).

L'envoi est silencieux : si Resend est down ou mal configure, on log
l'erreur et on retourne (False, message). L'admin peut toujours fallback
sur le magic_link copiable.
"""
import logging
from datetime import datetime

import httpx

from app.config import get_settings


logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"


def _format_dt_fr(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y a %Hh%M")


def _build_html(prenom: str, doc_type_libelle: str, magic_link: str, expires_at: datetime) -> str:
    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; color: #1A190F; background: #FAFAF7;">
  <h2 style="color: #2C6126; font-family: monospace;">Demande de document — Montpellier Depannage</h2>
  <p>Bonjour {prenom},</p>
  <p>Pour mettre a jour ton dossier d'habilitation, merci de nous transmettre ton document
     <strong>{doc_type_libelle}</strong> via le lien securise ci-dessous.</p>
  <p style="text-align: center; margin: 32px 0;">
    <a href="{magic_link}"
       style="background: #2C6126; color: #ffffff; padding: 14px 28px; text-decoration: none;
              border-radius: 4px; display: inline-block; font-weight: bold;">
      Envoyer mon document
    </a>
  </p>
  <p style="color: #6B6B5E; font-size: 13px;">
    Lien valable jusqu'au {_format_dt_fr(expires_at)}.<br>
    Si le bouton ne fonctionne pas, copie ce lien dans ton navigateur :<br>
    <span style="word-break: break-all; color: #2C6126;">{magic_link}</span>
  </p>
  <hr style="border: none; border-top: 1px solid #D3D1C7; margin: 32px 0;">
  <p style="color: #6B6B5E; font-size: 12px;">
    Email automatique. Si tu n'es pas le destinataire de ce message, ignore-le.
  </p>
</body>
</html>"""


def _build_text(prenom: str, doc_type_libelle: str, magic_link: str, expires_at: datetime) -> str:
    return (
        f"Bonjour {prenom},\n\n"
        f"Pour mettre a jour ton dossier d'habilitation, merci de nous transmettre "
        f"ton document {doc_type_libelle} via ce lien securise :\n\n"
        f"{magic_link}\n\n"
        f"Lien valable jusqu'au {_format_dt_fr(expires_at)}.\n\n"
        f"-- Montpellier Depannage"
    )


def send_magic_link_email(
    to: str,
    driver_prenom: str,
    doc_type_libelle: str,
    magic_link: str,
    expires_at: datetime,
) -> tuple[bool, str | None]:
    """Envoie l'email via Resend. Retourne (success, error_message)."""
    settings = get_settings()
    if not settings.resend_api_key:
        return False, "RESEND_API_KEY non configuree"

    payload: dict = {
        "from": settings.mail_from,
        "to": [to],
        "subject": f"Document a transmettre : {doc_type_libelle}",
        "html": _build_html(driver_prenom, doc_type_libelle, magic_link, expires_at),
        "text": _build_text(driver_prenom, doc_type_libelle, magic_link, expires_at),
    }
    if settings.mail_reply_to:
        payload["reply_to"] = settings.mail_reply_to

    try:
        res = httpx.post(
            RESEND_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("Resend HTTP error: %s", exc)
        return False, f"Reseau : {exc}"

    if res.status_code >= 400:
        logger.warning("Resend %s : %s", res.status_code, res.text)
        try:
            err = res.json().get("message") or res.text
        except Exception:
            err = res.text
        return False, f"Resend {res.status_code} : {err}"

    return True, None
