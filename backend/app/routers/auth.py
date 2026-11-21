"""Registration and login (JWT bearer tokens)."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import LoginIn, MeOut, RegisterIn, TokenOut
from app.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _token_for(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id), user=MeOut.model_validate(user))


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    clash = db.scalar(
        select(User).where(or_(User.email == email, func.lower(User.username) == body.username.lower()))
    )
    if clash:
        field = "email" if clash.email == email else "username"
        raise HTTPException(status.HTTP_409_CONFLICT, f"This {field} is already registered")
    user = User(
        email=email,
        username=body.username,
        display_name=body.display_name or body.username,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_for(user)


def _authenticate(db: Session, login: str, password: str) -> User:
    login = login.strip().lower()
    user = db.scalar(select(User).where(or_(User.email == login, func.lower(User.username) == login)))
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong e-mail/username or password")
    return user


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    return _token_for(_authenticate(db, body.login, body.password))


@router.post("/token", include_in_schema=True, summary="OAuth2 form login (used by the /docs Authorize button)")
def token(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = _authenticate(db, form.username, form.password)
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return user
