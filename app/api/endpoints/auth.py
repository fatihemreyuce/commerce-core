from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.core.deps import get_db, require_permission
from app.core.permissions import Permission
from app.core.config import settings
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    ALGORITHM,
)
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserLogin, AdminUserCreate, RefreshRequest

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """Yeni kullanıcı kaydı oluşturur."""
    
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu email adresi sistemde zaten kayıtlı."
        )
    
    hashed_password = get_password_hash(user_in.password)
    db_user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.post("/login")
def login(user_in: UserLogin, db: Session = Depends(get_db)):
    """Kullanıcı girişi yapar ve JWT Access Token döner."""
    
    user = db.query(User).filter(User.email == user_in.email).first()
    
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email adresi veya şifre hatalı."
        )
    
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role,
        },
    }


@router.post("/refresh")
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Geçerli bir refresh token karşılığında yeni access token üretir."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz veya süresi dolmuş yenileme token'ı.",
    )
    try:
        data = jwt.decode(payload.refresh_token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if data.get("type") != "refresh":
            raise credentials_exception
        user_id = data.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise credentials_exception

    new_access = create_access_token(subject=str(user.id))
    return {"access_token": new_access, "token_type": "bearer"}

@router.post("/admin/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def admin_create_user(
    user_in: AdminUserCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission(Permission.USER_MANAGE)),
):
    """Sadece adminlerin erişebildiği kullanıcı oluşturma (rol seçilebilir)."""

    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu email adresi sistemde zaten kayıtlı.",
        )

    db_user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user