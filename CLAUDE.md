# HABILITATION

Module 1MDP de suivi des habilitations des dépanneurs (B2XL, CACES, permis, carte conducteur). Cadrage fait le 2026-05-13, étape 1 (scaffold backend) livrée le même jour. Voir `README.md` pour le démarrage local.

## Stack

- **Backend** : FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL 16. **Toutes les routes sont préfixées par `/api`** (servies sous le même domaine que le frontend via le proxy nginx).
- **Auth admin** : JWT (python-jose) + bcrypt + TOTP (pyotp, optionnel)
- **Stockage fichiers** (dès étape 3) : filesystem chiffré Fernet
- **Relances** (étape 6) : n8n appelle le backend (cron)
- **Frontend** : React 18 + Vite (single-file `src/App.jsx` à la DepanTime). En prod, servi par nginx qui proxie aussi `/api/*` vers le backend (un seul domaine, pas de CORS).
- **Hébergement prod** : VPS Hetzner Ubuntu, voir [memory reference-vps]

## Périmètre MVP (figé au cadrage)

- 4 types de documents : `B2XL`, `CACES` (un seul), `PERMIS`, `CARTE_CONDUCTEUR`
- Tableau de bord matriciel dépanneurs × types, code couleur :
  - **Vert** : doc validé, > 90j de validité restante
  - **Orange** : doc validé, ≤ 90j de validité restante
  - **Rouge** : doc périmé OU applicable et jamais transmis
  - **Gris** : non applicable pour ce dépanneur
- Applicabilité par dépanneur via `driver_required_documents` (cochée par l'admin)
- **Saisie des dates manuelle** (pas d'OCR — décision explicite, à reprendre plus tard)
- Workflow validation : `pending` → `validated` / `rejected` par l'admin
- Versions archivées, **jamais d'écrasement** (impératif compliance URSSAF / Inspection du travail)
- Relances email J-90 / J-30 / J-7 + cas "jamais transmis"
- Dépanneur : **magic link à usage unique par demande**, pas de compte permanent
- App séparée de DepanTime, sync de la fiche dépanneur depuis DepanTime (mécanisme à préciser)
- Rétention par défaut 5 ans post-départ (configurable)

## État actuel de la roadmap

| # | Étape | Statut |
|---|---|---|
| 1 | Schéma Postgres + scaffold FastAPI + auth admin + CRUD basics | ✅ livré |
| 2 | Frontend React + endpoint `GET /dashboard` (matrice + statuts) | ✅ livré (2026-05-14) |
| 3 | Upload admin de documents (avec chiffrement Fernet) | ✅ livré (2026-05-14) |
| 4 | Flux dépanneur (demande → magic link → upload) | à faire |
| 5 | Validation admin (pending → validated/rejected) | à faire |
| 6 | Relances automatiques (n8n) | à faire |
| 7 | Historique versions + export PDF "état à date T" | à faire |
| 8 | RGPD : purge configurable post-départ, log d'accès | à faire |
| 9 | Déploiement prod (sous-domaine, TLS, sauvegardes) | 🟡 backend en ligne sur https://formations.alex-worksmart.com (TLS OK), sauvegardes Postgres restant à mettre en place |

## Conventions

- **Langue** : français pour tout ce qui est user-facing (libellés UI, messages d'erreur API, README). Code et noms techniques en anglais (variables, fonctions, classes, tables).
- **Pas de commentaires par défaut** : seulement si le WHY est non-évident (contrainte cachée, workaround, invariant subtil).
- **Pas d'over-engineering** : on construit ce qui est dans le périmètre de l'étape en cours. Pas d'abstractions anticipées pour les étapes suivantes.
- **Schéma complet dès l'étape 1** : toutes les tables MVP sont créées dans `alembic/versions/0001_initial.py`, même celles utilisées dans les étapes 3+. Cohérence du schéma > granularité des migrations.
- **Pas d'écrasement de documents** : un renouvellement = une nouvelle ligne dans `document_versions`, l'ancienne reste. C'est l'invariant compliance, ne pas le casser.

## Pièges connus

- **FK circulaire** `documents.current_version_id` ↔ `document_versions.document_id` : la migration la crée en deux temps (`use_alter=True` côté modèle + `op.create_foreign_key` après les deux tables côté migration).
- **bcrypt 72 octets** : `hash_password` lève `ValueError` si le password encodé UTF-8 dépasse 72 octets. Limite native de bcrypt, pas un bug.
- **Migrations auto au démarrage** : `docker-compose.yml` lance `alembic upgrade head` avant `uvicorn`. Toute migration commitée s'applique au prochain `docker compose up`.
- **JWT subject = UUID** : `payload["sub"]` est une string ; `db.get(AdminUser, payload["sub"])` fonctionne grâce à la conversion automatique de SQLAlchemy/psycopg.
- **Préfixe `/api` côté FastAPI** : toutes les routes sont déclarées sous `/api/...` dans `app/main.py`. Le frontend tape `/api/...` directement, et nginx proxie côté prod. Si tu ajoutes un router, n'oublie pas le préfixe `/api/...`.
- **`current_version` peut pointer vers une `pending`** en théorie. Le calcul du dashboard filtre explicitement sur `statut == VALIDATED` pour éviter qu'une version pas encore validée soit considérée comme la version active.
- **Traefik certresolver = `le`** (pas `cloudflare`). Cf [memory reference-vps].

## Commandes utiles

```powershell
# Build et démarrage local
docker compose up -d --build

# Logs backend (suivre)
docker compose logs -f backend

# Seed des 4 types de documents
docker compose exec backend python -m scripts.seed_doctypes

# Seed demo (3 dépanneurs avec cellules de chaque couleur — DEV UNIQUEMENT)
docker compose exec backend python -m scripts.seed_demo

# Frontend en dev (hors Docker)
cd frontend && npm install && npm run dev   # http://localhost:5173

# Création d'un admin
docker compose exec backend python -m scripts.create_admin --email a@1mdp.fr --name "X" --password "..."

# Nouvelle migration (autogénérée depuis les modèles)
docker compose exec backend alembic revision --autogenerate -m "message"
docker compose exec backend alembic upgrade head

# Reset complet (PERTE DE DONNÉES)
docker compose down -v
```

## Liens

- **Repo GitHub** : https://github.com/AlexDiLorenzo/Suivi-Formations
- **Domaine prod** : https://formations.alex-worksmart.com (à activer après bootstrap VPS)
- **DepanTime** (outil voisin, source de vérité des fiches dépanneurs) : `C:\Users\alexa\Desktop\BUSINESS\MTP_DEP\DEPANTIME\depantime-project\depantime\`
- Doc OpenAPI locale : `http://localhost:8000/docs` après `docker compose up`
