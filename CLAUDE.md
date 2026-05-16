# HABILITATION

Module 1MDP de suivi des habilitations et documents des dépanneurs (permis, FCO, B2XL, CACES, formations, documents administratifs). Cadrage fait le 2026-05-13, étape 1 (scaffold backend) livrée le même jour. Voir `README.md` pour le démarrage local.

## Stack

- **Backend** : FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL 16. **Toutes les routes sont préfixées par `/api`** (servies sous le même domaine que le frontend via le proxy nginx).
- **Auth admin** : JWT (python-jose) + bcrypt + TOTP (pyotp, optionnel)
- **Stockage fichiers** (dès étape 3) : filesystem chiffré Fernet
- **Relances** (étape 6) : n8n appelle le backend (cron)
- **Frontend** : React 18 + Vite (single-file `src/App.jsx` à la DepanTime). En prod, servi par nginx qui proxie aussi `/api/*` vers le backend (un seul domaine, pas de CORS).
- **Hébergement prod** : VPS Hetzner Ubuntu, voir [memory reference-vps]

## Périmètre fonctionnel

- **~20 types de documents** en 5 catégories (permis & conduite, CACES & autorisations, formations internes, diplômes, administratif RH). Au cadrage il n'y en avait que 4 — étendu à l'étape 10. Chaque `DocumentType` porte `categorie`, `est_perimable`, `criticite` (critique/standard), `mode_acquisition` (upload/docusign). Seed dans `scripts/seed_doctypes.py`.
- Tableau de bord matriciel dépanneurs × types, code couleur :
  - **Vert** : doc validé, > 90j de validité restante
  - **Orange** : doc validé, ≤ 90j de validité restante
  - **Rouge** : doc périmé OU applicable et jamais transmis
  - **Gris** : non applicable pour ce dépanneur
  - Documents **non-périmables** (RIB, CV, diplômes…) : pas de date → vert si validé, rouge si applicable et absent (jamais orange)
- Applicabilité par dépanneur via `driver_required_documents`. Le champ `profil` du dépanneur (permis B / permis C-CE) pré-coche les documents par défaut via `app/profils.py` ; l'admin ajuste ensuite case par case.
- **Scoring** (étape 10c) : score de conformité par dépanneur, pondéré critique (×3) / standard (×1), + taux global.
- **Saisie des dates manuelle** (pas d'OCR — décision explicite, à reprendre plus tard)
- Workflow validation : `pending` → `validated` / `rejected` par l'admin
- Versions archivées, **jamais d'écrasement** (impératif compliance URSSAF / Inspection du travail)
- Dépanneur : **magic link à usage unique par demande**, pas de compte permanent. ⏸️ Flux conservé mais dormant (décision étape 10) — tout est admin-uploadé. Exception à venir : l'attestation sur l'honneur passera par signature DocuSign (étape 10e).
- App séparée de DepanTime ; import des dépanneurs via `scripts/import_drivers_from_depantime.py` (import manuel à la demande depuis un CSV, pas de sync continu).
- Rétention par défaut 5 ans post-départ (configurable)

## État actuel de la roadmap

| # | Étape | Statut |
|---|---|---|
| 1 | Schéma Postgres + scaffold FastAPI + auth admin + CRUD basics | ✅ livré |
| 2 | Frontend React + endpoint `GET /dashboard` (matrice + statuts) | ✅ livré (2026-05-14) |
| 3 | Upload admin de documents (avec chiffrement Fernet) | ✅ livré (2026-05-14) |
| 4 | Flux dépanneur (demande → magic link → upload) | ✅ livré (2026-05-14, sans envoi email — link copiable côté admin) |
| 5 | Validation admin (pending → validated/rejected) | ✅ livré (2026-05-14) |
| 6 | Relances automatiques (n8n) | ⏸️ infra backend en place mais désactivée (REMINDERS_SECRET=vide). Décision 2026-05-14 : avec ~40 dépanneurs, relance téléphone manuelle préférée. Remplacé par fonctionnalité "demande groupée par dépanneur". |
| 7 | Historique versions + export PDF "état à date T" | à faire |
| 8 | RGPD : purge configurable post-départ, log d'accès | à faire |
| 9 | Déploiement prod (sous-domaine, TLS, sauvegardes) | 🟡 backend en ligne sur https://formations.alex-worksmart.com (TLS OK), sauvegardes Postgres restant à mettre en place |
| 10 | Évolution modèle documentaire (~20 types, profils, scoring, attestation DocuSign) | 🟡 en cours — 10a schéma ✅ (2026-05-15), 10b profil + applicabilité ✅ (2026-05-16). Reste : 10c scoring, 10d dashboard scores, 10e intégration DocuSign |

## Conventions

- **Langue** : français pour tout ce qui est user-facing (libellés UI, messages d'erreur API, README). Code et noms techniques en anglais (variables, fonctions, classes, tables).
- **Pas de commentaires par défaut** : seulement si le WHY est non-évident (contrainte cachée, workaround, invariant subtil).
- **Pas d'over-engineering** : on construit ce qui est dans le périmètre de l'étape en cours. Pas d'abstractions anticipées pour les étapes suivantes.
- **Schéma complet dès l'étape 1** : toutes les tables MVP sont créées dans `alembic/versions/0001_initial.py`, même celles utilisées dans les étapes 3+. Cohérence du schéma > granularité des migrations. Les évolutions post-MVP (ex: `0002` à l'étape 10) ajoutent leurs propres migrations additives.
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

# Seed des types de documents (~20, idempotent — supprime aussi les types obsolètes)
docker compose exec backend python -m scripts.seed_doctypes

# Seed demo (3 dépanneurs avec cellules de chaque couleur — DEV UNIQUEMENT)
docker compose exec backend python -m scripts.seed_demo

# Import des dépanneurs depuis un CSV exporté de DepanTime
docker compose exec backend python -m scripts.import_drivers_from_depantime --csv scripts/data/depantime_employees.csv

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
