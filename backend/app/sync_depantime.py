"""Synchronisation de la liste des depanneurs depuis DepanTime.

DepanTime tient les fiches de l'equipe ; cette application n'en est qu'un
consommateur. Un depanneur ajoute la-bas apparait ici, un depanneur archive
la-bas est archive ici. L'inverse n'est jamais vrai : rien n'est renvoye vers
DepanTime.

Ce qui appartient a DepanTime (ecrase a chaque passage) : nom, prenom, email,
date d'entree, statut actif/archive.
Ce qui appartient a HABILITATION (jamais touche par la synchro) : le profil de
permis, l'applicabilite des documents, et bien sur les documents eux-memes.

L'alignement est strict : une fiche absente de DepanTime n'a rien a faire dans
la liste, meme si elle a ete creee ici avant que la synchro existe. Deux sorts,
selon ce qu'elle porte :
  - elle detient des documents  -> archivee, jamais supprimee (les pieces de
    conformite doivent rester consultables apres le depart) ;
  - elle n'en detient aucun     -> supprimee, il n'y a rien a conserver.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Document,
    DocumentType,
    Driver,
    DriverRequiredDocument,
    DriverStatus,
)
from app.profils import DOCUMENTS_PAR_DEFAUT


class SyncError(RuntimeError):
    """Echec de la synchro — DepanTime injoignable, secret refuse, reponse illisible."""


@dataclass
class SyncResult:
    crees: int = 0
    mis_a_jour: int = 0
    archives: int = 0
    reactives: int = 0
    supprimes: int = 0
    ignores: list[str] = field(default_factory=list)
    hors_depantime: list[str] = field(default_factory=list)

    @property
    def total_traites(self) -> int:
        return self.crees + self.mis_a_jour + self.archives + self.reactives


def cle_externe(site_id: str, employee_id: str) -> str:
    """`employees.id` n'est unique que par site chez DepanTime (cle primaire
    composite) : la cle d'ici doit porter les deux."""
    return f"{site_id}:{employee_id}"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def recuperer_depanneurs() -> list[dict]:
    settings = get_settings()
    if not settings.depantime_sync_enabled:
        raise SyncError(
            "Synchronisation desactivee : renseigne DEPANTIME_BASE_URL et DEPANTIME_SECRET."
        )
    url = f"{settings.depantime_base_url.rstrip('/')}/api/habilitation-public/depanneurs"
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {settings.depantime_secret}"},
            timeout=settings.depantime_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise SyncError(f"DepanTime injoignable : {exc}") from exc

    if response.status_code == 401:
        raise SyncError("DepanTime a refuse le secret partage (401).")
    if response.status_code != 200:
        raise SyncError(f"DepanTime a repondu {response.status_code}.")

    try:
        payload = response.json()
    except ValueError as exc:
        raise SyncError("Reponse de DepanTime illisible (JSON invalide).") from exc

    depanneurs = payload.get("depanneurs")
    if not isinstance(depanneurs, list):
        raise SyncError("Reponse de DepanTime inattendue : cle 'depanneurs' absente.")
    return depanneurs


def _appliquer_socle(db: Session, driver: Driver) -> None:
    """Pose le socle de documents attendus sur un depanneur qui vient d'arriver.

    Sans cela un nouveau depanneur s'afficherait 100 % conforme, faute de
    document applicable — exactement l'inverse du signal recherche.
    """
    types = (
        db.query(DocumentType)
        .filter(DocumentType.code.in_(DOCUMENTS_PAR_DEFAUT))
        .all()
    )
    for doc_type in types:
        db.add(DriverRequiredDocument(driver_id=driver.id, document_type_id=doc_type.id))


def _driver_existant(db: Session, site_id: str, employee_id: str) -> Driver | None:
    """Retrouve le depanneur par sa cle externe.

    Les imports anterieurs ne stockaient que `employee_id` sans le site : on
    accepte encore cette forme et on la reecrit au format complet au passage.
    """
    cle = cle_externe(site_id, employee_id)
    driver = db.query(Driver).filter(Driver.external_id_depantime == cle).first()
    if driver:
        return driver
    legacy = db.query(Driver).filter(Driver.external_id_depantime == employee_id).first()
    if legacy:
        legacy.external_id_depantime = cle
    return legacy


def synchroniser(db: Session) -> SyncResult:
    depanneurs = recuperer_depanneurs()
    resultat = SyncResult()
    now = datetime.now(timezone.utc)
    vus: set[str] = set()

    for item in depanneurs:
        employee_id = str(item.get("id") or "").strip()
        site_id = str(item.get("site_id") or "").strip()
        nom = (item.get("nom") or "").strip()
        if not employee_id or not site_id or not nom:
            resultat.ignores.append(f"fiche incomplete : {item!r}")
            continue

        cle = cle_externe(site_id, employee_id)
        vus.add(cle)
        actif = item.get("active") is not False
        prenom = (item.get("prenom") or "").strip() or None
        email = (item.get("email") or "").strip() or None

        driver = _driver_existant(db, site_id, employee_id)
        if driver is None:
            driver = Driver(
                external_id_depantime=cle,
                nom=nom,
                prenom=prenom,
                email=email,
                date_entree=_parse_date(item.get("date_entree")),
                statut=DriverStatus.ACTIVE.value if actif else DriverStatus.ARCHIVED.value,
                last_sync_at=now,
            )
            db.add(driver)
            db.flush()
            _appliquer_socle(db, driver)
            resultat.crees += 1
            continue

        driver.nom = nom
        driver.prenom = prenom
        driver.email = email
        date_entree = _parse_date(item.get("date_entree"))
        if date_entree:
            driver.date_entree = date_entree
        driver.last_sync_at = now

        etait_actif = driver.statut == DriverStatus.ACTIVE.value
        if actif and not etait_actif:
            driver.statut = DriverStatus.ACTIVE.value
            driver.date_sortie = None
            resultat.reactives += 1
        elif not actif and etait_actif:
            driver.statut = DriverStatus.ARCHIVED.value
            if not driver.date_sortie:
                driver.date_sortie = date.today()
            resultat.archives += 1
        else:
            resultat.mis_a_jour += 1

    # Tout ce qui n'est pas dans DepanTime : fiches disparues de la-bas, et
    # fiches creees ici a la main avant que la synchro existe (cle nulle).
    for driver in db.query(Driver).all():
        if driver.external_id_depantime and driver.external_id_depantime in vus:
            continue

        nom = f"{driver.nom} {driver.prenom or ''}".strip()
        possede_des_pieces = (
            db.query(Document).filter(Document.driver_id == driver.id).count() > 0
        )
        if possede_des_pieces:
            if driver.statut == DriverStatus.ACTIVE.value:
                driver.statut = DriverStatus.ARCHIVED.value
                if not driver.date_sortie:
                    driver.date_sortie = date.today()
                driver.last_sync_at = now
                resultat.archives += 1
                resultat.hors_depantime.append(f"{nom} : archive (documents conserves)")
            continue

        # Aucune piece : la fiche ne porte rien, on l'efface pour que la liste
        # reste le reflet exact de DepanTime.
        db.delete(driver)
        resultat.supprimes += 1
        resultat.hors_depantime.append(f"{nom} : supprime (aucun document)")

    db.commit()
    return resultat
