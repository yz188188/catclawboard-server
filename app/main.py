import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.features.ztdb.router import router as ztdb_router
from app.features.jjztdt.router import router as jjztdt_router
from app.features.jjbvol.router import router as jjbvol_router
from app.features.effect.router import router as effect_router

logger = logging.getLogger(__name__)

app = FastAPI(title="CatClawBoard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://catclawboard.web.app",
        "https://nooka-cloudrun-250627.web.app",
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(ztdb_router)
app.include_router(jjztdt_router)
app.include_router(jjbvol_router)
app.include_router(effect_router)


@app.on_event("startup")
def seed_admin():
    from app.config import get_settings
    from app.database import SessionLocal
    from app.auth.models import User
    from app.auth.dependencies import hash_password

    settings = get_settings()
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()
        if not admin:
            admin = User(
                username=settings.ADMIN_USERNAME,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                password_plain=settings.ADMIN_PASSWORD,
                role="admin",
            )
            db.add(admin)
            db.commit()
            logger.info("管理员账号已创建: %s", settings.ADMIN_USERNAME)
        elif admin.role != "admin":
            admin.role = "admin"
            db.commit()
            logger.info("管理员账号角色已修正: %s", settings.ADMIN_USERNAME)
        else:
            logger.info("管理员账号已存在: %s", settings.ADMIN_USERNAME)
    finally:
        db.close()


@app.get("/health")
def health_check():
    return {"status": "ok"}
