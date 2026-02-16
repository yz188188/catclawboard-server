from pydantic import BaseModel


class MightyItem(BaseModel):
    id: int
    cdate: str
    stockid: str
    stockname: str | None = None
    scores: float | None = None
    times: str | None = None
    bzf: float | None = None
    cje: float | None = None
    rates: float | None = None
    ozf: float | None = None
    tms: str | None = None
    lastzf: float | None = None

    class Config:
        from_attributes = True


class MightyListResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list[MightyItem]
