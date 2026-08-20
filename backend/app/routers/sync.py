"""Declenchement de la synchronisation de l'equipe depuis DepanTime.

Deux portes d'entree pour la meme operation :
  - POST /api/sync/depantime          — bouton « Synchroniser » de l'application
  - POST /api/internal/sync/depantime — cron n8n (cf. routers/internal.py)
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_admin
from app.schemas import SyncStatusOut, SyncResultOut
from app.sync_depantime import SyncError, synchroniser


router = APIRouter(dependencies=[Depends(get_current_admin)])


def executer(db: Session) -> SyncResultOut:
    try:
        resultat = synchroniser(db)
    except SyncError as exc:
        # 502 et non 500 : la panne vient d'un service tiers, pas d'ici.
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return SyncResultOut(
        crees=resultat.crees,
        mis_a_jour=resultat.mis_a_jour,
        archives=resultat.archives,
        reactives=resultat.reactives,
        supprimes=resultat.supprimes,
        socle_poses=resultat.socle_poses,
        ignores=resultat.ignores,
        hors_depantime=resultat.hors_depantime,
    )


@router.get("/depantime", response_model=SyncStatusOut)
def statut_sync():
    settings = get_settings()
    sources = []
    if settings.depantime_sync_enabled:
        sources.append("DepanTime")
    if settings.flotte_sync_enabled:
        sources.append("Flotte (Pérols)")
    return SyncStatusOut(
        active=settings.sync_enabled,
        source=" + ".join(sources) or None,
    )


@router.post("/depantime", response_model=SyncResultOut)
def lancer_sync(db: Annotated[Session, Depends(get_db)]):
    return executer(db)
