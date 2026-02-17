from pydantic import BaseModel


class LianbanItem(BaseModel):
    id: int
    cdate: str
    stockid: str
    stockname: str | None = None
    lbs: int | None = None
    scores: float | None = None
    times: str | None = None
    bzf: float | None = None
    cje: float | None = None
    rates: float | None = None
    ozf: float | None = None
    zhenfu: float | None = None
    chg_1min: float | None = None
    zs_times: float | None = None
    tms: str | None = None
    lastzf: float | None = None

    class Config:
        from_attributes = True


class LianbanListResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list[LianbanItem]
