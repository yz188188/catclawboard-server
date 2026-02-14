from sqlalchemy import Column, Integer, String, DECIMAL

from app.database import Base


class MoneyEffect(Base):
    __tablename__ = "db_money_effects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cdate = Column(String(8), nullable=False, unique=True, index=True)
    ztje = Column(DECIMAL(15, 2), default=0)
    maxlb = Column(Integer, default=0)
    zts = Column(Integer, default=0)
    lbs = Column(Integer, default=0)
    yzb = Column(Integer, default=0)
    yzbfd = Column(DECIMAL(15, 2), default=0)
    dzfs = Column(Integer, default=0)
