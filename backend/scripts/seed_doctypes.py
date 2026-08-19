"""Seed des types de documents du suivi des habilitations.

Idempotent : upsert par code (cree si absent, met a jour sinon). Les types dont
le code n'est plus dans la liste sont supprimes — nettoyage des anciens types.
Les applicabilites (driver_required_documents) d'un type obsolete sont purgees
automatiquement (ce ne sont que de la config). En revanche la suppression echoue
si des documents reels y sont encore rattaches (FK RESTRICT) : c'est voulu, on
ne detruit pas des fichiers de conformite en silence — le type est alors laisse
en place avec un avertissement.

Deux axes portent l'affichage de la fiche depanneur :
  - `categorie`       : la famille (qui detient le document)
  - `niveau_exigence` : obligatoire / selon profil / complementaire

Le niveau est modifiable dans l'application ; ce seed ne fait que poser un
point de depart. Il n'ecrase donc PAS un niveau deja ajuste a la main
(cf. --reset-niveaux pour forcer le retour aux valeurs d'origine).
"""
import argparse

from app.db import SessionLocal
from app.models import (
    DocumentCategorie,
    DocumentModeAcquisition,
    DocumentNiveauExigence,
    DocumentType,
    DriverRequiredDocument,
    Document,
)


AN = 365


def _t(code, libelle, categorie, *, perimable, duree=None,
       niveau=DocumentNiveauExigence.COMPLEMENTAIRE,
       mode=DocumentModeAcquisition.UPLOAD, ordre):
    return {
        "code": code,
        "libelle": libelle,
        "categorie": categorie.value,
        "est_perimable": perimable,
        "duree_validite_jours_default": duree,
        "niveau_exigence": niveau.value,
        "mode_acquisition": mode.value,
        "display_order": ordre,
    }


_C = DocumentCategorie
_OBLIG = DocumentNiveauExigence.OBLIGATOIRE
_PROFIL = DocumentNiveauExigence.PROFIL

SEEDS = [
    # ── Conduite & permis ────────────────────────────────────────────
    _t("PERMIS", "Permis de conduire", _C.CONDUITE_PERMIS, perimable=True, duree=15 * AN, niveau=_OBLIG, ordre=10),
    _t("FIMO_FCO", "FIMO / FCO", _C.CONDUITE_PERMIS, perimable=True, duree=5 * AN, niveau=_PROFIL, ordre=20),
    _t("B2XL", "B2XL", _C.CONDUITE_PERMIS, perimable=True, duree=3 * AN, niveau=_PROFIL, ordre=30),
    _t("B1VL", "B1VL", _C.CONDUITE_PERMIS, perimable=True, duree=5 * AN, niveau=_PROFIL, ordre=40),

    # ── Habilitations & CACES ────────────────────────────────────────
    _t("AUTORISATION_CONDUITE", "Autorisation de conduite (entreprise)", _C.HABILITATIONS_CACES, perimable=True, duree=5 * AN, niveau=_OBLIG, ordre=50),
    _t("CACES_GRUE", "CACES grue", _C.HABILITATIONS_CACES, perimable=True, duree=5 * AN, niveau=_PROFIL, ordre=60),
    _t("CACES_CHARIOT", "CACES chariot elevateur", _C.HABILITATIONS_CACES, perimable=True, duree=5 * AN, niveau=_PROFIL, ordre=70),

    # ── Formations internes ──────────────────────────────────────────
    _t("FORMATION_INITIALE", "Formation initiale (interne)", _C.FORMATIONS_INTERNES, perimable=False, niveau=_OBLIG, ordre=80),
    _t("VINCI_EMA", "VINCI EMA", _C.FORMATIONS_INTERNES, perimable=False, ordre=90),
    _t("VINCI_AVA", "VINCI AVA", _C.FORMATIONS_INTERNES, perimable=False, ordre=100),

    # ── RH & administratif ───────────────────────────────────────────
    _t("PIECE_IDENTITE", "Piece d'identite (CNI ou passeport)", _C.RH_ADMINISTRATIF, perimable=True, duree=15 * AN, niveau=_OBLIG, ordre=110),
    _t("CONTRAT_TRAVAIL", "Contrat de travail", _C.RH_ADMINISTRATIF, perimable=False, niveau=_OBLIG, ordre=120),
    _t("DPAE", "DPAE (declaration prealable a l'embauche)", _C.RH_ADMINISTRATIF, perimable=False, niveau=_OBLIG, ordre=130),
    _t("JUSTIF_DOMICILE", "Justificatif de domicile", _C.RH_ADMINISTRATIF, perimable=False, ordre=140),
    _t("RIB", "RIB", _C.RH_ADMINISTRATIF, perimable=False, ordre=150),
    _t("MUTUELLE", "Mutuelle", _C.RH_ADMINISTRATIF, perimable=False, ordre=160),
    _t("CV", "CV", _C.RH_ADMINISTRATIF, perimable=False, ordre=170),
    _t("DIPLOMES", "Diplomes & titres (CAP, BEP, Bac Pro, BTS)", _C.RH_ADMINISTRATIF, perimable=False, ordre=180),
]

# Champs poses a chaque passage. `niveau_exigence` en est volontairement absent :
# il est reglable depuis l'application, un reseed ne doit pas defaire ce reglage.
_CHAMPS_TOUJOURS = (
    "libelle", "categorie", "est_perimable", "duree_validite_jours_default",
    "mode_acquisition", "display_order",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset-niveaux",
        action="store_true",
        help="Reapplique aussi les niveaux d'exigence d'origine (ecrase les reglages faits dans l'app)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        codes = {s["code"] for s in SEEDS}
        for seed in SEEDS:
            existing = db.query(DocumentType).filter(DocumentType.code == seed["code"]).first()
            if existing:
                for key in _CHAMPS_TOUJOURS:
                    setattr(existing, key, seed[key])
                if args.reset_niveaux:
                    existing.niveau_exigence = seed["niveau_exigence"]
                print(f"~ {seed['code']} mis a jour")
            else:
                db.add(DocumentType(**seed))
                print(f"+ {seed['code']}")

        for obsolete in db.query(DocumentType).filter(~DocumentType.code.in_(codes)).all():
            rattaches = (
                db.query(Document)
                .filter(Document.document_type_id == obsolete.id)
                .count()
            )
            if rattaches:
                print(
                    f"! {obsolete.code} conserve : {rattaches} document(s) reel(s) y sont "
                    "rattaches. Supprime-les d'abord si le type doit vraiment disparaitre."
                )
                continue
            db.query(DriverRequiredDocument).filter(
                DriverRequiredDocument.document_type_id == obsolete.id
            ).delete(synchronize_session=False)
            db.delete(obsolete)
            print(f"- {obsolete.code} supprime (obsolete, applicabilites purgees)")

        db.commit()
        print(f"\n{len(SEEDS)} types en place.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
