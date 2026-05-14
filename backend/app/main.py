from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, document_types, drivers, requirements


_settings = get_settings()


app = FastAPI(title="HABILITATION API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "env": _settings.env}


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(drivers.router, prefix="/drivers", tags=["drivers"])
app.include_router(document_types.router, prefix="/document-types", tags=["document-types"])
app.include_router(requirements.router, prefix="/requirements", tags=["requirements"])
