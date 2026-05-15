from fastapi import APIRouter, Depends

from app.deps import get_current_admin
from app.models import DriverProfil
from app.profils import PROFIL_DOCUMENTS
from app.schemas import ProfilOut


router = APIRouter(dependencies=[Depends(get_current_admin)])

_LABELS = {
    DriverProfil.PERMIS_B.value: "Permis B",
    DriverProfil.PERMIS_C_CE.value: "Permis C / CE",
}


@router.get("", response_model=list[ProfilOut])
def list_profils():
    return [
        ProfilOut(value=value, label=_LABELS[value], document_codes=codes)
        for value, codes in PROFIL_DOCUMENTS.items()
    ]
