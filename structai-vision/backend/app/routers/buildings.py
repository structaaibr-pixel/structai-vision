from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Building, User
from ..schemas import BuildingCreate, BuildingOut

router = APIRouter(prefix="/buildings", tags=["buildings"])


@router.post("", response_model=BuildingOut, status_code=201)
def create_building(body: BuildingCreate, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    b = Building(owner_id=user.id, name=body.name, address=body.address)
    db.add(b)
    db.commit()
    return b


@router.get("", response_model=list[BuildingOut])
def list_buildings(db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    return db.scalars(select(Building).where(Building.owner_id == user.id)).all()


def get_owned_building(building_id: int, db: Session, user: User) -> Building:
    b = db.get(Building, building_id)
    if b is None or b.owner_id != user.id:
        raise HTTPException(404, "prédio não encontrado")
    return b
