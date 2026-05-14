"""Seed de demo pour visualiser le tableau de bord en local.

Cree 3 depanneurs avec des applicabilites variees et des document_versions
de differents statuts/dates de peremption pour generer des cellules vert /
orange / rouge / gris.

Idempotent : detecte les depanneurs deja seed (par external_id_depantime)
et skip si deja presents. Ne PAS lancer en prod.

Usage :
    docker compose exec backend python -m scripts.seed_demo
"""
from datetime import date, timedelta

from app.db import SessionLocal
from app.models import (
    Document,
    DocumentType,
    DocumentVersion,
    DocumentVersionStatus,
    Driver,
    DriverRequiredDocument,
    UploadedBy,
)


DEMO_TAG = "demo-"

DRIVERS = [
    {"external_id_depantime": f"{DEMO_TAG}001", "prenom": "Marc", "nom": "Aubert"},
    {"external_id_depantime": f"{DEMO_TAG}002", "prenom": "Lucie", "nom": "Bernard"},
    {"external_id_depantime": f"{DEMO_TAG}003", "prenom": "Julien", "nom": "Cordier"},
]


def _fake_version(doc_id, peremption_offset_days, statut=DocumentVersionStatus.VALIDATED):
    today = date.today()
    return DocumentVersion(
        document_id=doc_id,
        file_path_encrypted="DEMO_NO_FILE",
        file_sha256="0" * 64,
        file_size_bytes=0,
        original_filename="demo.pdf",
        mime_type="application/pdf",
        date_emission=today - timedelta(days=365),
        date_peremption=today + timedelta(days=peremption_offset_days),
        uploaded_by=UploadedBy.ADMIN.value,
        statut=statut.value,
    )


def main() -> None:
    db = SessionLocal()
    try:
        doctypes = {dt.code: dt for dt in db.query(DocumentType).all()}
        if not doctypes:
            raise SystemExit("Lance d'abord scripts.seed_doctypes")

        for seed in DRIVERS:
            existing = (
                db.query(Driver)
                .filter(Driver.external_id_depantime == seed["external_id_depantime"])
                .first()
            )
            if existing:
                print(f"= {seed['prenom']} {seed['nom']} deja present")
                continue
            driver = Driver(**seed)
            db.add(driver)
            db.flush()
            print(f"+ depanneur {driver.prenom} {driver.nom}")

            # Marc : tout applicable, mix vert / orange / rouge / rouge-jamais-recu
            # Lucie : 2 types applicables, 1 vert + 1 orange
            # Julien : 3 types applicables, dont 1 sans version (rouge-jamais-recu)
            if seed["external_id_depantime"] == f"{DEMO_TAG}001":
                plan = {
                    "B2XL": +400,            # vert
                    "CACES": +60,            # orange
                    "PERMIS": -10,           # rouge - expire
                    "CARTE_CONDUCTEUR": None,  # rouge - jamais recu
                }
            elif seed["external_id_depantime"] == f"{DEMO_TAG}002":
                plan = {
                    "B2XL": +800,            # vert
                    "PERMIS": +45,           # orange
                    # CACES et CARTE_CONDUCTEUR : non applicables (gris)
                }
            else:  # 003
                plan = {
                    "CACES": +200,           # vert
                    "PERMIS": -120,          # rouge - expire (vieux)
                    "CARTE_CONDUCTEUR": None,  # rouge - jamais recu
                    # B2XL : non applicable (gris)
                }

            for code, offset in plan.items():
                dt = doctypes[code]
                db.add(DriverRequiredDocument(driver_id=driver.id, document_type_id=dt.id))
                if offset is None:
                    continue
                doc = Document(driver_id=driver.id, document_type_id=dt.id)
                db.add(doc)
                db.flush()
                version = _fake_version(doc.id, offset)
                db.add(version)
                db.flush()
                doc.current_version_id = version.id

        db.commit()
        print("OK")
    finally:
        db.close()


if __name__ == "__main__":
    main()
