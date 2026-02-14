from sqlalchemy import Column, Integer, String, DECIMAL

from app.database import Base


class Ztdb(Base):
    __tablename__ = "db_ztdb"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cdate = Column(String(8), nullable=False, index=True)
    stockid = Column(String(20), nullable=False)
    stockname = Column(String(50))
    zhenfu = Column(DECIMAL(10, 2))
    declines = Column(DECIMAL(10, 2))
