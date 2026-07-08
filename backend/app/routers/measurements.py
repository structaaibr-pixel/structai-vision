from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Capture, Measurement, User
from ..schemas import MeasurementOut
from .buildings import get_owned_building

router = APIRouter(tags=["measurements"])


@router.get("/captures/{capture_id}/measurement", response_model=MeasurementOut)
def get_measurement(capture_id: int, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    c = db.get(Capture, capture_id)
    if c is None:
        raise HTTPException(404, "captura não encontrada")
    get_owned_building(c.building_id, db, user)
    m = db.scalar(select(Measurement).where(Measurement.capture_id == capture_id))
    if m is None:
        raise HTTPException(404, f"sem medição ainda (status: {c.status.value})"
                            + (f" — erro: {c.error}" if c.error else ""))
    return m
