"""Mapping profil de permis -> codes de documents requis par defaut.

Sert au pre-remplissage de driver_required_documents quand l'admin choisit un
profil pour un depanneur. L'admin peut ensuite ajuster manuellement, document
par document : ce mapping n'est qu'un point de depart raisonnable.
"""
from app.models import DriverProfil


# Documents attendus de tout depanneur, quel que soit le profil de permis.
_COMMUNS = [
    "PERMIS",
    "ATTESTATION_PERMIS",
    "FORMATION_INITIALE",
    "VINCI_EMA",
    "VINCI_AVA",
    "DIPLOMES",
    "CNI",
    "JUSTIF_DOMICILE",
    "RIB",
    "CV",
    "CONTRAT_TRAVAIL",
    "DPAE",
    "MUTUELLE",
]

# B1VL est optionnel chez 1MDP (meme pour les permis C/CE) : volontairement
# absent des pre-remplissages, l'admin le coche au cas par cas si besoin.
PROFIL_DOCUMENTS: dict[str, list[str]] = {
    DriverProfil.PERMIS_C_CE.value: _COMMUNS + [
        "FIMO_FCO",
        "B2XL",
        "CACES_GRUE",
        "CACES_CHARIOT",
        "AUTORISATION_CONDUITE",
    ],
    DriverProfil.PERMIS_B.value: _COMMUNS + [
        "AUTORISATION_CONDUITE",
    ],
}
