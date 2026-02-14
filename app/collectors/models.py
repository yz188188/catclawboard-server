# coding:utf-8
from sqlalchemy import Column, Integer, String, DECIMAL, UniqueConstraint

from app.database import Base


class ZtReson(Base):
    __tablename__ = "db_zt_reson"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cdate = Column(String(8), nullable=False, index=True)
    stockid = Column(String(20), nullable=False)
    stockname = Column(String(50))
    cje = Column(DECIMAL(15, 2), default=0)
    lbs = Column(Integer, default=0)
    reson = Column(String(200))

    __table_args__ = (
        UniqueConstraint("cdate", "stockid", name="uk_cdate_stockid"),
    )
