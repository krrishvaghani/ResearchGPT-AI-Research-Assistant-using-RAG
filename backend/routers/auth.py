from fastapi import APIRouter, Depends, HTTPException, status
import bcrypt
from sqlalchemy.orm import Session

from auth.jwt_handler import create_access_token
from db.database import get_db
from db.models import User
from models.schemas import TokenResponse, UserCreate, UserLogin

router = APIRouter()


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """Create a new user account and return a JWT access token."""
    exists = (
        db.query(User)
        .filter((User.username == user_in.username) | (User.email == user_in.email))
        .first()
    )
    if exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email is already registered.",
        )
    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=_hash(user_in.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": user.username})
    return TokenResponse(access_token=token, token_type="bearer", username=user.username)


@router.post("/login", response_model=TokenResponse)
async def login(user_in: UserLogin, db: Session = Depends(get_db)):
    """Authenticate and return a JWT access token."""
    user = db.query(User).filter(User.username == user_in.username).first()
    if user is None or not _verify(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )
    token = create_access_token({"sub": user.username})
    return TokenResponse(access_token=token, token_type="bearer", username=user.username)
