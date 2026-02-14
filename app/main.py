from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.features.ztdb.router import router as ztdb_router
from app.features.jjztdt.router import router as jjztdt_router
from app.features.jjbvol.router import router as jjbvol_router
from app.features.effect.router import router as effect_router

app = FastAPI(title="CatClawBoard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(ztdb_router)
app.include_router(jjztdt_router)
app.include_router(jjbvol_router)
app.include_router(effect_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
