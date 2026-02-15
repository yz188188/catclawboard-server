from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    id: int
    username: str
    role: str

    class Config:
        from_attributes = True


class UserInfoAdmin(BaseModel):
    id: int
    username: str
    role: str
    password_plain: str
    created_at: datetime

    class Config:
        from_attributes = True
