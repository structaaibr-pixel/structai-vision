from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/token")


def hash_password(p: str) -> str:
    return pwd.hash(p)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd.verify(plain, hashed)


def create_token(user_id: int) -> str:
    exp = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": exp},
                      settings.jwt_secret, algorithm="HS256")


def get_current_user(token: str = Depends(oauth2),
                     db: Session = Depends(get_db)) -> User:
    cred_exc = HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciais inválidas")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id = int(payload.get("sub", 0))
    except (JWTError, ValueError):
        raise cred_exc
    user = db.get(User, user_id)
    if user is None:
        raise cred_exc
    return user
