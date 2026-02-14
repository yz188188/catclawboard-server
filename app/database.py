from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import get_settings

settings = get_settings()


def _build_engine():
    """根据环境构建数据库引擎。

    Cloud Run 环境: 通过 INSTANCE_CONNECTION_NAME 使用 Unix socket 连接 Cloud SQL
    本地环境: 直接使用 DATABASE_URL (TCP 连接)
    """
    if settings.INSTANCE_CONNECTION_NAME:
        if not settings.DB_USER or not settings.DB_PASS:
            raise ValueError("Cloud SQL 模式需要设置 DB_USER 和 DB_PASS 环境变量")
        # Cloud Run: 通过内置 Cloud SQL Proxy 的 Unix socket 连接
        socket_path = f"/cloudsql/{settings.INSTANCE_CONNECTION_NAME}"
        url = (
            f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASS}"
            f"@/{settings.DB_NAME}?unix_socket={socket_path}"
        )
        return create_engine(url, pool_pre_ping=True, pool_recycle=300)

    # 本地: 直接 TCP 连接
    return create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_recycle=300)


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
