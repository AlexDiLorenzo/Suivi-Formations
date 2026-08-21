"""Seed des types de documents du suivi des habilitations.

Idempotent : upsert par code (cree si absent, met a jour sinon). Les types dont
le code n'est plus dans la liste sont supprimes — nettoyage des anciens types.
Les applicabilites (driver_required_documents) d'un type obsolete sont purgees
automatiquement (ce ne sont que de la config). En revanche la suppression echoue
si des documents reels y sont encore rattaches (FK RESTRICT) : c'est voulu, on
ne detruit pas des fichiers de conformite en silence — le type est alors laisse
en place avec un avertissement.

Trois axes decrivent chaque type :

  - `categorie`       : la famille, qui dit qui detient le document
  - `niveau_exigence` : SOCLE (sans lui, on ne roule pas — seul niveau compte
                        dans le taux de conformite) ou COMPLEMENTAIRE (valorise
                        le profil, suivi par un second indicateur)
  - `perimetre`       : a qui un document du socle s'applique. `tous` par
                        defaut ; `asf` et `poids_lourd` sont **derives** des
                        attributs synchronises depuis DepanTime, jamais coches.
                        Sans effet sur un complementaire, propose a tout le monde.

Ce fichier est la seule source de verite de ces trois axes : rien de tout cela
n'est reglable depuis l'application. Un reseed les reapplique tels quels.
"""
from app.db import SessionLocal
from app.models import (
    DocumentCategorie,
    DocumentModeAcquisition,
    DocumentNiveauExigence,
    DocumentPerimetre,
    DocumentType,
    DriverRequiredDocument,
    Document,
)


AN = 365


def _t(code, libelle, categorie, *, perimable, duree=None,
       niveau=DocumentNiveauExigence.COMPLEMENTAIRE,
       perimetre=DocumentPerimetre.TOUS,
       mode=DocumentModeAcquisition.UPLOAD, ordre):
    return {
        "code": code,
        "libelle": libelle,
        "categorie": categorie.value,
        "est_perimable": perimable,
        "duree_validite_jours_default": duree,
        "niveau_exigence": niveau.value,
        "perimetre": perimetre.value,
        "mode_acquisition": mode.value,
        "display_order": ordre,
    }


_C = DocumentCategorie
_SOCLE = DocumentNiveauExigence.SOCLE
_ASF = DocumentPerimetre.ASF
_PL = DocumentPerimetre.POIDS_LOURD

SEEDS = [
    # ══ SOCLE — tout le monde ════════════════════════════════════════
    _t("PERMIS", "Permis de conduire", _C.CONDUITE_PERMIS,
       perimable=True, duree=15 * AN, niveau=_SOCLE, ordre=10),
    _t("PIECE_IDENTITE", "Pièce d'identité (CNI ou passeport)", _C.RH_ADMINISTRATIF,
       perimable=True, duree=15 * AN, niveau=_SOCLE, ordre=20),
    # Un CDI produit un contrat de travail, un interimaire un contrat de mise a
    # disposition remis a jour a chaque mission : c'est le meme creneau du
    # dossier, deux types en feraient un rouge permanent chez chacun des deux.
    _t("CONTRAT_TRAVAIL", "Contrat de travail ou de mise à disposition", _C.RH_ADMINISTRATIF,
       perimable=False, niveau=_SOCLE, ordre=30),
    _t("DPAE", "DPAE (déclaration préalable à l'embauche)", _C.RH_ADMINISTRATIF,
       perimable=False, niveau=_SOCLE, ordre=40),
    _t("MUTUELLE", "Carte vitale / mutuelle", _C.RH_ADMINISTRATIF,
       perimable=False, niveau=_SOCLE, ordre=50),
    # Formation initiale et formation interne sont une seule et meme chose : le
    # parcours qui rend quelqu'un apte a depanner chez 1MDP (bases du metier,
    # vehicules electriques, securite, semaine en binome). C'est ce qui protege
    # l'entreprise en cas de litige et devant la medecine du travail, d'ou sa
    # place au socle — CDI comme interimaire.
    #
    # Perimable sans duree par defaut : la revisite ne suit pas un cycle fixe,
    # elle se declenche sur evenement (passage au permis B, module manquant).
    # La date se saisit au depot et l'alerte orange a 90 j fait le rappel.
    #
    # Le code reste `FORMATION_INITIALE` : il porte deja des pieces reelles.
    _t("FORMATION_INITIALE", "Formation initiale 1MDP (dépannage, véhicules électriques, sécurité)",
       _C.FORMATIONS_INTERNES, perimable=True, niveau=_SOCLE, ordre=60),

    # ══ SOCLE — equipe ASF ═══════════════════════════════════════════
    # Pas d'AVA, pas d'autoroute : le seul document que l'appartenance a
    # l'equipe ASF rend bloquant. EMA est une bonne formation, prise en charge
    # par l'etat, mais son absence n'empeche personne de rouler : elle est
    # complementaire, y compris pour les ASF.
    _t("VINCI_AVA", "VINCI AVA", _C.FORMATIONS_INTERNES,
       perimable=True, duree=3 * AN, niveau=_SOCLE, perimetre=_ASF, ordre=70),

    # ══ SOCLE — poids lourd ══════════════════════════════════════════
    # Le permis lourd se fait revalider tous les 5 ans, visite medicale a
    # l'appui — la date portee sur le permis fait foi.
    _t("PERMIS_PL", "Permis C / CE (poids lourd)", _C.CONDUITE_PERMIS,
       perimable=True, duree=5 * AN, niveau=_SOCLE, perimetre=_PL, ordre=100),

    # ══ COMPLEMENTAIRES ══════════════════════════════════════════════
    # La FCO ne conditionne pas le permis C : elle vaut qualification, pas
    # autorisation. Son vrai enjeu est ailleurs — la laisser perimer oblige a
    # repasser la FIMO, soit 30 jours de formation au lieu d'un recyclage.
    _t("FIMO_FCO", "FIMO / FCO", _C.CONDUITE_PERMIS,
       perimable=True, duree=5 * AN, ordre=200),
    # La piece qui compte est le titre d'habilitation, pas l'attestation de
    # formation : c'est lui qui autorise a intervenir.
    _t("B2XL", "B2XL (titre d'habilitation)", _C.CONDUITE_PERMIS,
       perimable=True, duree=3 * AN, ordre=210),
    _t("B1VL", "B1VL (habilitation électrique)", _C.CONDUITE_PERMIS,
       perimable=True, duree=5 * AN, ordre=220),
    _t("CACES_GRUE", "CACES R490 (grue auxiliaire)", _C.HABILITATIONS_CACES,
       perimable=True, duree=5 * AN, ordre=230),
    _t("CACES_CHARIOT", "CACES R489 (chariot élévateur)", _C.HABILITATIONS_CACES,
       perimable=True, duree=5 * AN, ordre=240),
    # Le CACES atteste du stage, il n'autorise pas a conduire dans l'entreprise :
    # c'est le chef d'entreprise qui signe l'autorisation. Complementaire par
    # consequence — elle suit les CACES, elle ne bloque personne seule.
    _t("AUTORISATION_CONDUITE", "Autorisation de conduite (signée par l'employeur)",
       _C.HABILITATIONS_CACES, perimable=True, duree=5 * AN, ordre=250),
    # Dispensee par VINCI et prise en charge par l'etat, mais rien n'empeche de
    # rouler sans elle — d'ou sa place ici plutot qu'au socle ASF, ou seul AVA
    # est bloquant.
    _t("VINCI_EMA", "VINCI EMA", _C.FORMATIONS_INTERNES,
       perimable=True, duree=5 * AN, ordre=255),
    # Le code reste `FORMATION_SECURITE` : ce type existe depuis longtemps et
    # porte deja des pieces reelles. Un code neuf en aurait fait un doublon vide
    # a cote, et les documents deposes seraient restes accroches a l'ancien.
    _t("FORMATION_SECURITE", "Formation sécurité VINCI", _C.FORMATIONS_INTERNES,
       perimable=False, ordre=260),
    # Pour les depanneurs qui ne sont pas ressortissants de l'UE. Perimable sans
    # duree par defaut : elle est portee par le titre lui-meme.
    _t("AUTORISATION_TRAVAIL", "Autorisation de travail / titre de séjour",
       _C.RH_ADMINISTRATIF, perimable=True, ordre=270),
    _t("JUSTIF_DOMICILE", "Justificatif de domicile", _C.RH_ADMINISTRATIF,
       perimable=False, ordre=280),
    _t("RIB", "RIB", _C.RH_ADMINISTRATIF, perimable=False, ordre=290),
    _t("CV", "CV", _C.RH_ADMINISTRATIF, perimable=False, ordre=300),
    _t("DIPLOMES", "Diplômes & titres (CAP, BEP, Bac Pro, BTS)", _C.RH_ADMINISTRATIF,
       perimable=False, ordre=310),
]

_CHAMPS = (
    "libelle", "categorie", "est_perimable", "duree_validite_jours_default",
    "niveau_exigence", "perimetre", "mode_acquisition", "display_order",
)


def main() -> None:
    db = SessionLocal()
    try:
        codes = {s["code"] for s in SEEDS}
        for seed in SEEDS:
            existing = db.query(DocumentType).filter(DocumentType.code == seed["code"]).first()
            if existing:
                for key in _CHAMPS:
                    setattr(existing, key, seed[key])
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
        socle = sum(1 for s in SEEDS if s["niveau_exigence"] == DocumentNiveauExigence.SOCLE.value)
        print(f"\n{len(SEEDS)} types en place — {socle} au socle, {len(SEEDS) - socle} complementaires.")
        print("Pense a relancer la synchro : c'est elle qui pose les nouvelles exigences.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
