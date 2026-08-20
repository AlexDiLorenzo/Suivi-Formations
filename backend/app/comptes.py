"""Comptes administrateurs — déclaratifs, comme dans les autres applications.

Les comptes ne se créent PAS depuis l'application : ils sont déclarés ici et
leur mot de passe vient du .env du serveur (/srv/habilitation/.env), réappliqué
à chaque démarrage de l'API. Même mécanisme que Depantime, Caisse, Flotte et
Pilotage.

Ajouter quelqu'un : une ligne dans COMPTES, une ligne HB_PASS_<PRENOM> dans le
.env, puis `cd /srv/habilitation && docker compose -f docker-compose.prod.yml up -d`.

Sans variable d'environnement, le compte n'est pas créé — jamais de mot de
passe par défaut.
"""
import logging
import os

from app.db import SessionLocal
from app.models import AdminUser
from app.security import hash_password

logger = logging.getLogger(__name__)

# (adresse, nom affiché, variable d'environnement)
COMPTES = [
    ("alexandre.dilorenzo.pro@gmail.com", "Alexandre", "HB_PASS_ALEXANDRE"),
    ("norbert.dilorenzo@montpellierdepannage.com", "Norbert", "HB_PASS_NORBERT"),
    ("sandrine@montpellierdepannage.com", "Sandrine", "HB_PASS_SANDRINE"),
    ("compta@montpellierdepannage.com", "Marie", "HB_PASS_MARIE"),
    # Acces ad-hoc : pas de compte dans le coffre-fort, mot de passe dictable.
    ("frank@montpellierdepannage.com", "Frank", "HB_PASS_FRANK"),
]


def amorcer_comptes() -> None:
    """Crée ou met à jour les comptes déclarés. Appelé au démarrage."""
    db = SessionLocal()
    try:
        declares = set()
        for email, nom, cle_env in COMPTES:
            email = email.lower().strip()
            declares.add(email)
            mot_de_passe = os.getenv(cle_env)
            if not mot_de_passe:
                continue
            admin = db.query(AdminUser).filter(AdminUser.email == email).first()
            if admin:
                admin.password_hash = hash_password(mot_de_passe)
                admin.full_name = nom
            else:
                db.add(AdminUser(email=email, full_name=nom,
                                 password_hash=hash_password(mot_de_passe)))
            logger.info("compte applique : %s", email)
        db.commit()

        # Les comptes hors liste sont signalés, jamais supprimés : une faute de
        # frappe dans le .env ne doit pas fermer l'accès à tout le monde.
        orphelins = [a.email for a in db.query(AdminUser).all()
                     if a.email.lower() not in declares]
        if orphelins:
            logger.warning("comptes hors liste (ni créés ni supprimés) : %s",
                           ", ".join(orphelins))
    except Exception:
        db.rollback()
        # Un échec d'amorçage ne doit pas empêcher l'API de démarrer : les
        # comptes existants restent utilisables.
        logger.exception("amorçage des comptes impossible")
    finally:
        db.close()
