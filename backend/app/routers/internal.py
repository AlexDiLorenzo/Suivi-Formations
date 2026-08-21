"""Endpoint interne : forcer une synchronisation de l'equipe.

Auth via header X-Internal-Secret (pas de JWT, pas de cookie), donc
REMINDERS_SECRET doit etre renseigne. Si le secret est vide, cet endpoint
repond 503 — la synchronisation periodique, elle, continue de tourner.

Ce n'est **pas** ce qui fait tourner la synchro : elle est portee par
`app/scheduler.py`, dans l'application. Cet endpoint ne sert qu'a ne pas
attendre le tour suivant, typiquement apres avoir corrige une equipe ou un type
de vehicule dans DepanTime.

Les relances par email passaient aussi par ici (`/reminders/due`,
`/reminders/mark-sent`) : elles ont ete retirees avec les workflows n8n
(2026-08-21), sans jamais avoir servi — aucune ligne n'avait ete ecrite dans
`reminders` ni dans `document_requests`. L'etape 13 les remplacera par un mail
des documents manquants, qui ne s'y prendra pas de la meme facon.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import verify_internal_secret
from app.schemas import SyncResultOut
from app.sync_depantime import SyncError, synchroniser


router = APIRouter(dependencies=[Depends(verify_internal_secret)])


@router.post("/sync/depantime", response_model=SyncResultOut)
def sync_depantime(db: Annotated[Session, Depends(get_db)]):
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
        exigences_posees=resultat.exigences_posees,
        exigences_retirees=resultat.exigences_retirees,
        ignores=resultat.ignores,
        hors_depantime=resultat.hors_depantime,
    )
