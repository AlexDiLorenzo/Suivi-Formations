"""Importe les depanneurs depuis un CSV exporte de DepanTime.

CSV attendu (colonnes obligatoires) : id, prenom, nom, email

Genere depuis DepanTime :
    docker exec depantime-db psql -U depantime -d depantime \\
      -c "\\COPY (SELECT id, prenom, nom, email FROM employees) TO STDOUT WITH CSV HEADER" \\
      > depantime_employees.csv

L'import est idempotent : pour chaque ligne, on cherche un Driver par external_id_depantime,
on l'update si trouve, on le cree sinon. Telephone, dates d'entree/sortie et applicabilite des
documents (DriverRequiredDocument) sont a completer manuellement cote HABILITATION apres l'import.

Usage :
    python -m scripts.import_drivers_from_depantime --csv scripts/data/depantime_employees.csv
"""
import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.db import SessionLocal
from app.models import Driver, DriverStatus


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="Chemin du CSV exporte de DepanTime")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Erreur : fichier introuvable : {csv_path}", file=sys.stderr)
        sys.exit(1)

    created = updated = skipped = 0
    db = SessionLocal()
    try:
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ext_id = _normalize(row.get("id"))
                prenom = _normalize(row.get("prenom"))
                nom = _normalize(row.get("nom"))
                email = _normalize(row.get("email"))

                if not ext_id or not prenom or not nom:
                    print(f"= ignore (id/prenom/nom manquant) : {row}")
                    skipped += 1
                    continue

                existing = db.query(Driver).filter(Driver.external_id_depantime == ext_id).first()
                now = datetime.now(timezone.utc)
                if existing:
                    existing.prenom = prenom
                    existing.nom = nom
                    existing.email = email
                    existing.last_sync_at = now
                    print(f"~ mis a jour : {prenom} {nom} ({ext_id})")
                    updated += 1
                else:
                    db.add(Driver(
                        external_id_depantime=ext_id,
                        prenom=prenom,
                        nom=nom,
                        email=email,
                        statut=DriverStatus.ACTIVE.value,
                        last_sync_at=now,
                    ))
                    print(f"+ cree : {prenom} {nom} ({ext_id})")
                    created += 1

        db.commit()
        print(f"\nResultat : {created} crees, {updated} mis a jour, {skipped} ignores")
    finally:
        db.close()


if __name__ == "__main__":
    main()
