from sqlalchemy import Column, Integer, String, DECIMAL

from app.database import Base


class Jjztdt(Base):
    __tablename__ = "db_data_jjztdt"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cdate = Column(String(8), nullable=False, unique=True, index=True)
    zts = Column(Integer, default=0)
    ztfd = Column(DECIMAL(15, 2), default=0)
    dts = Column(Integer, default=0)
    dtfd = Column(DECIMAL(15, 2), default=0)
