"""Seed des types de documents du suivi des habilitations.

Idempotent : upsert par code (cree si absent, met a jour sinon). Les types dont
le code n'est plus dans la liste sont supprimes — nettoyage des anciens types.
La suppression echoue si des documents y sont encore rattaches (FK RESTRICT) :
c'est voulu, on ne supprime pas un type encore utilise.
"""
from app.db import SessionLocal
from app.models import (
    DocumentCategorie,
    DocumentCriticite,
    DocumentModeAcquisition,
    DocumentType,
)


AN = 365


def _t(code, libelle, categorie, *, perimable, duree=None,
       criticite=DocumentCriticite.STANDARD,
       mode=DocumentModeAcquisition.UPLOAD, ordre):
    return {
        "code": code,
        "libelle": libelle,
        "categorie": categorie.value,
        "est_perimable": perimable,
        "duree_validite_jours_default": duree,
        "criticite": criticite.value,
        "mode_acquisition": mode.value,
        "display_order": ordre,
    }


_C = DocumentCategorie
_CRIT = DocumentCriticite.CRITIQUE
_DOCUSIGN = DocumentModeAcquisition.DOCUSIGN

SEEDS = [
    _t("PERMIS", "Permis de conduire", _C.PERMIS_CONDUITE, perimable=True, duree=5 * AN, criticite=_CRIT, ordre=10),
    _t("ATTESTATION_PERMIS", "Attestation sur l'honneur de validite du permis", _C.PERMIS_CONDUITE, perimable=True, duree=90, mode=_DOCUSIGN, ordre=20),
    _t("FIMO_FCO", "FIMO / FCO", _C.PERMIS_CONDUITE, perimable=True, duree=5 * AN, criticite=_CRIT, ordre=30),
    _t("B2XL", "B2XL", _C.PERMIS_CONDUITE, perimable=True, duree=5 * AN, criticite=_CRIT, ordre=40),
    _t("B1VL", "B1VL", _C.PERMIS_CONDUITE, perimable=True, duree=5 * AN, criticite=_CRIT, ordre=50),
    _t("CACES_GRUE", "CACES grue", _C.CACES_AUTORISATIONS, perimable=True, duree=5 * AN, criticite=_CRIT, ordre=60),
    _t("CACES_CHARIOT", "CACES chariot elevateur", _C.CACES_AUTORISATIONS, perimable=True, duree=5 * AN, criticite=_CRIT, ordre=70),
    _t("AUTORISATION_CONDUITE", "Autorisation de conduite (entreprise)", _C.CACES_AUTORISATIONS, perimable=True, duree=5 * AN, criticite=_CRIT, ordre=80),
    _t("FORMATION_INITIALE", "Formation initiale (interne)", _C.FORMATIONS_INTERNES, perimable=False, ordre=90),
    _t("FORMATION_SECURITE", "Formation complementaire / securite", _C.FORMATIONS_INTERNES, perimable=False, ordre=100),
    _t("VINCI_EMA", "VINCI EMA", _C.FORMATIONS_INTERNES, perimable=False, ordre=110),
    _t("VINCI_AVA", "VINCI AVA", _C.FORMATIONS_INTERNES, perimable=False, ordre=120),
    _t("DIPLOMES", "Diplomes & titres (CAP, BEP, Bac Pro, BTS)", _C.DIPLOMES, perimable=False, ordre=130),
    _t("CNI", "Carte nationale d'identite", _C.ADMINISTRATIF, perimable=True, duree=15 * AN, ordre=140),
    _t("JUSTIF_DOMICILE", "Justificatif de domicile", _C.ADMINISTRATIF, perimable=False, ordre=150),
    _t("RIB", "RIB", _C.ADMINISTRATIF, perimable=False, ordre=160),
    _t("CV", "CV", _C.ADMINISTRATIF, perimable=False, ordre=170),
    _t("CONTRAT_TRAVAIL", "Contrat de travail", _C.ADMINISTRATIF, perimable=False, ordre=180),
    _t("DPAE", "DPAE (declaration prealable a l'embauche)", _C.ADMINISTRATIF, perimable=False, ordre=190),
    _t("MUTUELLE", "Mutuelle", _C.ADMINISTRATIF, perimable=False, ordre=200),
]


def main() -> None:
    db = SessionLocal()
    try:
        codes = {s["code"] for s in SEEDS}
        for seed in SEEDS:
            existing = db.query(DocumentType).filter(DocumentType.code == seed["code"]).first()
            if existing:
                for key, value in seed.items():
                    setattr(existing, key, value)
                print(f"~ {seed['code']} mis a jour")
            else:
                db.add(DocumentType(**seed))
                print(f"+ {seed['code']}")
        for obsolete in db.query(DocumentType).filter(~DocumentType.code.in_(codes)).all():
            db.delete(obsolete)
            print(f"- {obsolete.code} supprime (obsolete)")
        db.commit()
        print(f"\n{len(SEEDS)} types en place.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
