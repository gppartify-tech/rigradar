"""User profiles: your own settings + everyone's public seller profile."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import JORDAN_CITIES
from app.database import get_db
from app.models import Listing, User
from app.schemas import MeOut, PasswordChangeIn, ProfileUpdateIn, PublicProfileOut, PublicUserOut
from app.security import get_current_user, hash_password, verify_password
from app.services.uploads import delete_upload, save_image

router = APIRouter(prefix="/api/users", tags=["users"])


@router.patch("/me", response_model=MeOut)
def update_me(body: ProfileUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    if data.get("city") and data["city"] not in JORDAN_CITIES:
        raise HTTPException(422, "Unknown city")
    for key, value in data.items():
        if key in ("bio", "city", "phone") and not value:
            value = None  # an empty string clears the field
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


@router.post("/me/password", status_code=204)
def change_password(body: PasswordChangeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is wrong")
    user.password_hash = hash_password(body.new_password)
    db.commit()


@router.post("/me/avatar", response_model=MeOut)
def upload_avatar(
    file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    url = save_image(file, "avatars", max_side=400)
    delete_upload(user.avatar_url)
    user.avatar_url = url
    db.commit()
    db.refresh(user)
    return user


@router.get("/{username}", response_model=PublicProfileOut)
def public_profile(username: str, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.username) == username.lower()))
    if user is None:
        raise HTTPException(404, "User not found")
    counts = dict(
        db.execute(
            select(Listing.status, func.count()).where(Listing.seller_id == user.id).group_by(Listing.status)
        ).all()
    )
    return PublicProfileOut(
        **PublicUserOut.model_validate(user).model_dump(),
        active_listings=counts.get("active", 0),
        sold_listings=counts.get("sold", 0),
    )
