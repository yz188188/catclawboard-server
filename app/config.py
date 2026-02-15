from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 本地 TCP 连接 (本地开发 / Windows collectors 使用)
    DATABASE_URL: str = "mysql+pymysql://root:dbywl168@127.0.0.1:3306/catclawboard"

    # Cloud SQL 连接 (Cloud Run 使用，设置后优先于 DATABASE_URL)
    INSTANCE_CONNECTION_NAME: str = ""  # 格式: project:region:instance
    DB_USER: str = "root"
    DB_PASS: str = ""
    DB_NAME: str = "catclawboard"

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours
    THS_USERNAME: str = ""
    THS_PASSWORD: str = ""

    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "yz188188"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
