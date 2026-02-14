from decimal import Decimal
from pydantic import BaseModel


class EffectItem(BaseModel):
    id: int
    cdate: str
    ztje: Decimal = Decimal("0")
    maxlb: int = 0
    zts: int = 0
    lbs: int = 0
    yzb: int = 0
    yzbfd: Decimal = Decimal("0")
    dzfs: int = 0

    class Config:
        from_attributes = True


class EffectListResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list[EffectItem]
