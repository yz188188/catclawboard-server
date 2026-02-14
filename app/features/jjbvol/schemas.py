from decimal import Decimal
from pydantic import BaseModel


class JjbvolItem(BaseModel):
    id: int
    cdate: str
    stockid: str
    stockname: str | None = None
    zf: Decimal | None = None
    zs: Decimal | None = None
    volume: int = 0
    jje: Decimal = Decimal("0")
    rate: Decimal = Decimal("0")
    status: str | None = None

    class Config:
        from_attributes = True


class JjbvolListResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list[JjbvolItem]
