"""Endpoint de pilotage appele par le dashboard du site web.

Auth via header X-Pilotage-Secret (pas de JWT). Necessite PILOTAGE_SECRET
dans `.env`. Expose le taux de conformite documentaire global, deja calcule
par le dashboard admin -- on reutilise `get_dashboard` pour ne pas dupliquer
la logique de scoring (poids critique x3 / standard x1).
"""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import verify_pilotage_secret
from app.routers.dashboard import get_dashboard


router = APIRouter(dependencies=[Depends(verify_pilotage_secret)])


@router.get("/snapshot")
def pilotage_snapshot(db: Annotated[Session, Depends(get_db)]):
    result = get_dashboard(db)
    summary = result.summary
    by_status = {
        getattr(status, "value", status): count
        for status, count in summary.by_status.items()
    }
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "score_global": summary.score_global,
        "drivers_total": len(result.drivers),
        "by_status": by_status,
    }
