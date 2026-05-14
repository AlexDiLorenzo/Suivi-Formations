"""Cree un admin.

Usage:
    python -m scripts.create_admin --email vous@1mdp.fr --name "Votre Nom" --password "..."
"""
import argparse
import sys

from app.db import SessionLocal
from app.models import AdminUser
from app.security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    email = args.email.lower().strip()
    db = SessionLocal()
    try:
        if db.query(AdminUser).filter(AdminUser.email == email).first():
            print(f"Erreur : un admin avec l'email {email} existe deja", file=sys.stderr)
            sys.exit(1)
        admin = AdminUser(
            email=email,
            full_name=args.name,
            password_hash=hash_password(args.password),
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print(f"Admin cree : {admin.email} (id={admin.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
