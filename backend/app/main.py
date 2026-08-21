from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import scheduler
from app.comptes import amorcer_comptes
from app.config import get_settings
from app.routers import (
    auth,
    dashboard,
    docusign,
    document_requests,
    document_types,
    documents,
    drivers,
    internal,
    pilotage,
)


_settings = get_settings()


app = FastAPI(title="HABILITATION API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _amorcage():
    """Applique les comptes déclarés dans app/comptes.py.

    Les migrations Alembic tournent avant le lancement d'uvicorn (voir la
    commande du compose), la table admin_users existe donc déjà ici.
    """
    amorcer_comptes()
    # La synchro de l'équipe est portée par l'application : il n'y a plus de
    # workflow n8n, et plus de bouton non plus. Cf. app/scheduler.py.
    scheduler.demarrer()


@app.on_event("shutdown")
async def _extinction():
    await scheduler.arreter()


@app.get("/api/health", tags=["meta"])
def health():
    """Etat de l'application, et surtout de la derniere synchronisation.

    Une synchro muette est invisible depuis l'interface — tout y a l'air à
    jour. C'est le seul endroit où on peut s'en apercevoir.
    """
    return {
        "status": "ok",
        "env": _settings.env,
        "sync": scheduler.dernier_resultat,
    }


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(drivers.router, prefix="/api/drivers", tags=["drivers"])
app.include_router(document_types.router, prefix="/api/document-types", tags=["document-types"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(
    document_requests.admin_router,
    prefix="/api/document-requests",
    tags=["document-requests"],
)
app.include_router(
    document_requests.public_router,
    prefix="/api/public/document-requests",
    tags=["public"],
)
app.include_router(internal.router, prefix="/api/internal", tags=["internal"])
app.include_router(pilotage.router, prefix="/api/pilotage", tags=["pilotage"])
app.include_router(docusign.router, prefix="/api/docusign", tags=["docusign"])
