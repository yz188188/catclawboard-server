from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.models import User
from app.auth.schemas import (
    LoginRequest,
    UserCreate,
    TokenResponse,
    UserInfo,
    UserInfoAdmin,
    SubscriptionUpdate,
)
from app.auth.dependencies import create_access_token, get_current_user, get_current_admin

router = APIRouter(prefix="/auth", tags=["auth"])

SUBSCRIPTION_DAYS = {"monthly": 30, "yearly": 365}


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or user.password != req.password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    user.token_version += 1
    db.commit()
    token = create_access_token({"sub": user.username, "tv": user.token_version})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserInfo)
def get_me(user: User = Depends(get_current_user)):
    return user


@router.get("/users", response_model=List[UserInfoAdmin])
def list_users(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return db.query(User).order_by(User.id).all()


@router.post("/users", response_model=UserInfoAdmin)
def create_user(req: UserCreate, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
    user = User(username=req.username, password=req.password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    if admin.id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除自己")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    db.delete(user)
    db.commit()
    return {"detail": "已删除"}


@router.post("/users/{user_id}/subscription", response_model=UserInfoAdmin)
def set_subscription(
    user_id: int,
    req: SubscriptionUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if req.subscription_type not in SUBSCRIPTION_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="订阅类型无效，可选: monthly, yearly",
        )
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if user.role == "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="管理员无需设置订阅")

    days = SUBSCRIPTION_DAYS[req.subscription_type]
    now = datetime.now()

    if user.subscription_end and user.subscription_end > now:
        start_from = user.subscription_end
    else:
        start_from = now
        user.subscription_start = now

    user.subscription_type = req.subscription_type
    user.subscription_end = start_from + timedelta(days=days)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}/subscription", response_model=UserInfoAdmin)
def cancel_subscription(
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if user.role == "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="管理员无需管理订阅")

    user.subscription_type = None
    user.subscription_start = None
    user.subscription_end = None
    db.commit()
    db.refresh(user)
    return user
