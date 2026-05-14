"""Seed les 4 types de documents du MVP."""
from app.db import SessionLocal
from app.models import DocumentType


SEEDS = [
    {"code": "B2XL", "libelle": "B2XL (permis poids lourd)", "duree_validite_jours_default": 5 * 365, "display_order": 10},
    {"code": "CACES", "libelle": "CACES", "duree_validite_jours_default": 5 * 365, "display_order": 20},
    {"code": "PERMIS", "libelle": "Permis de conduire", "duree_validite_jours_default": 15 * 365, "display_order": 30},
    {"code": "CARTE_CONDUCTEUR", "libelle": "Carte de conducteur", "duree_validite_jours_default": 5 * 365, "display_order": 40},
]


def main() -> None:
    db = SessionLocal()
    try:
        for seed in SEEDS:
            existing = db.query(DocumentType).filter(DocumentType.code == seed["code"]).first()
            if existing:
                print(f"= {seed['code']} deja present")
                continue
            db.add(DocumentType(**seed))
            print(f"+ {seed['code']}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
