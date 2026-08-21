"""Ce qu'on attend d'un depanneur — et de qui on l'attend.

Deux niveaux, et deux seulement (cf. `DocumentNiveauExigence`) :

  - le **socle**, sans lequel le depanneur ne roule pas. C'est le seul a
    entrer dans le taux de conformite ;
  - le **complementaire**, qui valorise le profil et se suit a part.

Rien ne se coche nulle part. L'applicabilite est **entierement derivee** des
attributs synchronises depuis DepanTime : un document du socle porte un
`perimetre` (`tous`, `asf`, `poids_lourd`) confronte a l'equipe et au type de
vehicule de la personne. C'est la difference avec l'ancien niveau `profil`, qui
se reglait document par document sur chaque fiche et derivait des la premiere
arrivee ou mutation oubliee.

Les complementaires, eux, sont proposes a tout le monde : leur perimetre est
sans effet. Il faut bien pouvoir deposer un CACES a quelqu'un qui vient de le
passer, sans l'avoir declare grutier au prealable.
"""
from sqlalchemy.orm import Session

from app.models import (
    EQUIPE_ASF,
    PROFIL_VEHICULE_POIDS_LOURD,
    Document,
    DocumentNiveauExigence,
    DocumentPerimetre,
    DocumentType,
    Driver,
    DriverRequiredDocument,
)

_SOCLE = DocumentNiveauExigence.SOCLE.value


def perimetres_du_driver(driver: Driver) -> set[str]:
    """Les perimetres auxquels cette personne appartient.

    `tous` en fait toujours partie : c'est le socle commun, il n'a pas de
    condition. Les autres s'ajoutent selon ce que DepanTime tient a jour.
    """
    perimetres = {DocumentPerimetre.TOUS.value}
    if driver.equipe == EQUIPE_ASF:
        perimetres.add(DocumentPerimetre.ASF.value)
    if driver.profil_vehicule == PROFIL_VEHICULE_POIDS_LOURD:
        perimetres.add(DocumentPerimetre.POIDS_LOURD.value)
    return perimetres


def types_applicables(db: Session, driver: Driver) -> set:
    """Ids des types de documents attendus de ce depanneur."""
    perimetres = perimetres_du_driver(driver)
    return {
        t.id
        for t in db.query(DocumentType).all()
        if t.niveau_exigence != _SOCLE or t.perimetre in perimetres
    }


def reconcilier(db: Session, driver: Driver) -> tuple[int, int]:
    """Aligne l'applicabilite de ce depanneur sur ce que son perimetre exige.

    Renvoie `(ajoutes, retires)`. Contrairement a l'ancienne application du
    socle, purement additive, celle-ci **retire** aussi : quelqu'un qui quitte
    l'equipe ASF ne doit plus etre compte non conforme faute d'AVA.

    Un retrait n'est jamais fait si une piece a deja ete deposee pour ce type.
    Un CACES reste rattache a son dossier meme si la personne change d'affectation
    — l'exigence disparait, la trace de conformite non.
    """
    voulus = types_applicables(db, driver)
    existants = {
        r.document_type_id: r
        for r in db.query(DriverRequiredDocument).filter(
            DriverRequiredDocument.driver_id == driver.id
        )
    }

    ajoutes = 0
    for type_id in voulus - set(existants):
        db.add(DriverRequiredDocument(driver_id=driver.id, document_type_id=type_id))
        ajoutes += 1

    en_trop = set(existants) - voulus
    retires = 0
    if en_trop:
        avec_piece = {
            d.document_type_id
            for d in db.query(Document)
            .filter(Document.driver_id == driver.id)
            .filter(Document.document_type_id.in_(en_trop))
        }
        for type_id in en_trop - avec_piece:
            db.delete(existants[type_id])
            retires += 1

    return ajoutes, retires
