"""Endpoint de pilotage appele par le dashboard du site web.

Auth via header X-Pilotage-Secret (pas de JWT). Necessite PILOTAGE_SECRET
dans `.env`. Expose le taux de conformite documentaire global, deja calcule
par le dashboard admin -- on reutilise `get_dashboard` pour ne pas dupliquer
la logique de scoring.

`score_global` porte desormais la conformite au **socle** seul (etape 14) : il
peut donc bouger a la hausse d'un coup, les complementaires ayant quitte le
calcul. La qualification est renvoyee a part, sans etre agregee dedans.
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
        "qualification_acquises": summary.qualification_acquises,
        "qualification_total": summary.qualification_total,
        "drivers_total": len(result.drivers),
        "by_status": by_status,
    }
