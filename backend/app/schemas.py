from datetime import datetime

from pydantic import BaseModel, EmailStr

from .models import CaptureSource, CaptureStatus


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class BuildingCreate(BaseModel):
    name: str
    address: str | None = None


class BuildingOut(BuildingCreate):
    id: int
    created_at: datetime
    model_config = {"from_attributes": True}


class CaptureOut(BaseModel):
    id: int
    building_id: int
    source: CaptureSource
    status: CaptureStatus
    image_count: int
    has_gcp: bool
    has_video: bool = False
    error: str | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class MeasurementOut(BaseModel):
    capture_id: int
    surface_area_m2: float
    height_m: float
    footprint_perimeter_m: float
    mesh_key: str | None = None
    pointcloud_key: str | None = None
    created_at: datetime
    model_config = {"from_attributes": True}
