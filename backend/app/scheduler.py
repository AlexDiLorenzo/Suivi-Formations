"""Synchronisation periodique de l'equipe, tenue par l'application elle-meme.

Elle etait declenchee par un cron n8n ; il n'y a plus de workflow n8n
(2026-08-21) et le bouton « Synchroniser » a ete retire a l'etape 14. Sans ce
scheduler, plus rien n'alignerait la liste : elle se figerait sans que rien ne
le signale, ce qui est exactement le mode de panne qu'on cherche a eviter — une
application qui a l'air a jour et ne l'est pas.

Le faire porter par le backend plutot que par un ordonnanceur exterieur enleve
la dependance a un service tiers, et surtout garantit que ca redemarre avec
l'application : un conteneur qui tourne est un conteneur qui synchronise.

Une seule replique du backend tourne (`container_name` fixe dans le compose) :
pas de verrou a poser, deux instances se marcheraient sinon dessus.
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.config import get_settings
from app.db import SessionLocal
from app.sync_depantime import SyncError, synchroniser


logger = logging.getLogger("habilitation.sync")

_tache: asyncio.Task | None = None

# Etat de la derniere tentative, expose par /api/health : c'est le seul endroit
# ou une synchro muette depuis des jours peut encore se voir.
dernier_resultat: dict = {"etat": "jamais_executee"}


def _synchroniser_une_fois() -> dict:
    """Un passage complet. Bloquant : appele via `asyncio.to_thread`."""
    db = SessionLocal()
    try:
        r = synchroniser(db)
        return {
            "etat": "ok",
            "horodatage": datetime.now(timezone.utc).isoformat(),
            "crees": r.crees,
            "mis_a_jour": r.mis_a_jour,
            "archives": r.archives,
            "supprimes": r.supprimes,
            "exigences_posees": r.exigences_posees,
            "exigences_retirees": r.exigences_retirees,
        }
    finally:
        db.close()


async def _boucle() -> None:
    settings = get_settings()
    interval = max(60, settings.sync_interval_minutes * 60)

    # Court delai avant la premiere passe : le temps que Postgres finisse de
    # repondre au healthcheck et que les migrations soient derriere nous.
    await asyncio.sleep(settings.sync_delai_demarrage_secondes)

    while True:
        global dernier_resultat
        try:
            dernier_resultat = await asyncio.to_thread(_synchroniser_une_fois)
            logger.info("Synchro : %s", dernier_resultat)
        except SyncError as exc:
            # Source injoignable ou secret refuse : rien n'a ete ecrit (la
            # synchro echoue avant, par construction). On retentera au prochain
            # tour plutot que d'arreter la boucle.
            dernier_resultat = {
                "etat": "echec",
                "horodatage": datetime.now(timezone.utc).isoformat(),
                "erreur": str(exc),
            }
            logger.warning("Synchro impossible : %s", exc)
        except Exception:
            dernier_resultat = {
                "etat": "erreur",
                "horodatage": datetime.now(timezone.utc).isoformat(),
            }
            logger.exception("Synchro : erreur inattendue")

        await asyncio.sleep(interval)


def demarrer() -> None:
    global _tache
    settings = get_settings()
    if not settings.sync_enabled:
        logger.info("Synchro periodique inactive : aucune source configuree.")
        return
    if _tache and not _tache.done():
        return
    _tache = asyncio.create_task(_boucle())
    logger.info(
        "Synchro periodique activee : toutes les %s minutes.",
        settings.sync_interval_minutes,
    )


async def arreter() -> None:
    if _tache and not _tache.done():
        _tache.cancel()
        try:
            await _tache
        except asyncio.CancelledError:
            pass
