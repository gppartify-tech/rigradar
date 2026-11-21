"""PC builder: compatibility check + budget recommendation."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Product
from app.schemas import BuildCheckIn, BuildCheckOut, RecommendIn, RecommendOut
from app.services.compatibility import build_report
from app.services.recommender import recommend

router = APIRouter(prefix="/api/builds", tags=["builder"])


@router.post("/check", response_model=BuildCheckOut)
def check_build(body: BuildCheckIn, db: Session = Depends(get_db)):
    products = db.scalars(
        select(Product).where(Product.id.in_(body.product_ids)).options(selectinload(Product.best_store))
    ).all()
    if not products:
        raise HTTPException(404, "No products found")
    parts: dict[str, Product] = {}
    for p in products:
        if p.category in parts:
            raise HTTPException(422, f"Only one {p.category} per build")
        parts[p.category] = p
    return build_report(parts)


@router.post("/recommend", response_model=RecommendOut)
def recommend_build(body: RecommendIn, db: Session = Depends(get_db)):
    return recommend(db, body)
