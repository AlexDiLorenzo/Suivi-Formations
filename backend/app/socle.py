"""Le socle : ce qui est attendu de tout depanneur, sans exception.

Il n'est **pas** parametrable depuis l'application. C'est le seed des types
(`scripts/seed_doctypes.py`) qui en decide, via `niveau_exigence` :

  - tout ce qui n'est pas une habilitation appartient au socle et s'applique a
    tout le monde, automatiquement, a chaque synchronisation ;
  - les **habilitations** (niveau `profil` : FIMO/FCO, B2XL, B1VL, CACES) se
    cochent au cas par cas, ce sont les seules a dependre de la personne.

L'application du socle est **additive** : elle pose ce qui manque et ne retire
jamais rien. Decocher une habilitation reste donc possible, decocher un
document du socle non — la synchro suivante le remettrait de toute facon.
"""
from sqlalchemy.orm import Session

from app.models import DocumentNiveauExigence, DocumentType, DriverRequiredDocument

# Seul niveau qui se coche a la main.
NIVEAU_A_COCHER = DocumentNiveauExigence.PROFIL.value


def types_du_socle(db: Session) -> list[DocumentType]:
    return (
        db.query(DocumentType)
        .filter(DocumentType.niveau_exigence != NIVEAU_A_COCHER)
        .all()
    )


def ids_du_socle(db: Session) -> set:
    return {t.id for t in types_du_socle(db)}


def appliquer_socle(db: Session, driver_id) -> int:
    """Pose les documents du socle manquants pour ce depanneur.

    Renvoie le nombre d'ajouts. N'ecrit rien s'il n'y a rien a ajouter.
    """
    deja = {
        r.document_type_id
        for r in db.query(DriverRequiredDocument).filter(
            DriverRequiredDocument.driver_id == driver_id
        )
    }
    ajoutes = 0
    for type_id in ids_du_socle(db) - deja:
        db.add(DriverRequiredDocument(driver_id=driver_id, document_type_id=type_id))
        ajoutes += 1
    return ajoutes
