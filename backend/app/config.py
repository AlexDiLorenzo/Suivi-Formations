from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 12  # 12h
    file_encryption_key: str
    cors_origins: str = "http://localhost:5173"
    env: str = "dev"

    documents_storage_path: str = "/var/lib/habilitation/documents"
    orange_threshold_days: int = 90

    # Secret partage avec n8n pour les endpoints internes (relances).
    # Si vide, les endpoints internes sont desactives.
    reminders_secret: str = ""

    # Base URL du frontend, utilisee pour construire les magic_link
    # dans les emails de relance (n8n appelle l'API mais le mail doit
    # pointer vers le frontend).
    frontend_base_url: str = "http://localhost:5173"

    # Cadence des relances "jamais transmis" (en jours).
    never_received_grace_days: int = 7
    never_received_interval_days: int = 7

    # Envoi d'email via Resend (https://resend.com).
    # Si RESEND_API_KEY est vide, l'envoi est desactive et l'admin
    # devra copier le magic_link manuellement.
    resend_api_key: str = ""
    mail_from: str = "Habilitations 1MDP <habilitations@example.com>"
    mail_reply_to: str = ""

    # ---- DocuSign (signature de l'attestation sur l'honneur, etape 10e) ----
    # Authentification JWT Grant (server-to-server). Si une des 4 valeurs
    # ci-dessous est vide, l'integration DocuSign est consideree desactivee.
    docusign_integration_key: str = ""
    docusign_user_id: str = ""
    docusign_account_id: str = ""
    # Cle privee RSA (PEM). Peut contenir des "\n" litteraux (cas .env Docker).
    docusign_private_key: str = ""
    docusign_template_id: str = "6da048a0-92a0-458e-a0e8-a2ae33090940"
    docusign_role_name: str = "Salarie"
    # "production" -> account.docusign.com | "demo" -> account-d.docusign.com
    docusign_env: str = "production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def docusign_enabled(self) -> bool:
        return all(
            [
                self.docusign_integration_key,
                self.docusign_user_id,
                self.docusign_account_id,
                self.docusign_private_key,
                self.docusign_template_id,
            ]
        )

    @property
    def docusign_oauth_host(self) -> str:
        return "account-d.docusign.com" if self.docusign_env == "demo" else "account.docusign.com"

    @property
    def docusign_private_key_pem(self) -> str:
        # Restaure les vrais retours a la ligne si la cle a ete passee
        # sur une seule ligne avec des "\n" echappes (frequent en .env).
        return self.docusign_private_key.replace("\\n", "\n")


@lru_cache
def get_settings() -> Settings:
    return Settings()
