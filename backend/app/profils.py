"""Habilitations attendues selon le profil de permis.

Le **socle** (identite, permis, contrat, RH...) est pose automatiquement sur
tout le monde par `app/socle.py` : il n'a pas sa place ici. Ce mapping ne
couvre que les **habilitations**, les seules a se cocher au cas par cas, et
ne sert qu'a les pre-cocher quand l'admin choisit un profil. L'ajustement
reste manuel ensuite.

Les niveaux d'exigence eux-memes sont imposes par le seed des types
(`scripts/seed_doctypes.py`), pas reglables depuis l'application.
"""
from app.models import DriverProfil


# B1VL est optionnel chez 1MDP, meme pour les permis C/CE : volontairement
# absent des pre-cochages, l'admin le coche au cas par cas si besoin.
PROFIL_DOCUMENTS: dict[str, list[str]] = {
    DriverProfil.PERMIS_C_CE.value: [
        "FIMO_FCO",
        "B2XL",
        "CACES_GRUE",
        "CACES_CHARIOT",
    ],
    DriverProfil.PERMIS_B.value: [],
}
