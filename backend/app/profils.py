"""Mapping profil de permis -> codes de documents requis par defaut.

Sert au pre-remplissage de driver_required_documents quand l'admin choisit un
profil pour un depanneur — et a l'initialisation d'un depanneur cree par la
synchro DepanTime. L'admin peut ensuite ajuster manuellement, document par
document : ce mapping n'est qu'un point de depart raisonnable.
"""
from app.models import DriverProfil


# Socle attendu de tout depanneur, quel que soit le profil de permis.
# Aligne sur les types de niveau `obligatoire` du seed, plus les pieces RH
# systematiquement reunies a l'embauche.
_COMMUNS = [
    "PERMIS",
    "AUTORISATION_CONDUITE",
    "FORMATION_INITIALE",
    "PIECE_IDENTITE",
    "CONTRAT_TRAVAIL",
    "DPAE",
    "JUSTIF_DOMICILE",
    "RIB",
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
    ],
    DriverProfil.PERMIS_B.value: list(_COMMUNS),
}

# Applique aux depanneurs crees par la synchro, dont le profil de permis n'est
# pas connu : seulement le socle, l'admin precise le profil ensuite.
DOCUMENTS_PAR_DEFAUT = list(_COMMUNS)
