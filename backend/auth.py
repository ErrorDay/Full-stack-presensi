"""Shared local authentication for SQLAdmin and FastAPI endpoints."""

import uuid

from fastapi import Depends, HTTPException, status
from passlib.context import CryptContext
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from database.models import User
from database.session import SessionLocal

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ROLES = ["admin", "operator", "walas"]


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _authenticate_user(username: str, password: str) -> User | None:
    if not username or not password:
        return None

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is None or not user.password_hash:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user
    finally:
        db.close()


class AdminAuth(AuthenticationBackend):
    """Login handler shared by SQLAdmin and API session authentication."""

    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            return False

        user = _authenticate_user(username, password)
        if user is None:
            return False

        request.session.clear()
        request.session.update(
            {
                "user_id": str(user.id),
                "username": user.username,
                "nama": user.nama,
                "role": user.role,
                "kelas_id": str(user.kelas_id) if user.kelas_id else None,
            }
        )
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return "user_id" in request.session


def require_login(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Belum login. Silakan login terlebih dahulu.",
        )
    try:
        parsed_user_id = uuid.UUID(str(user_id))
    except (TypeError, ValueError) as exc:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesi login tidak valid. Silakan login kembali.",
        ) from exc

    return {
        "user_id": parsed_user_id,
        "username": request.session.get("username"),
        "nama": request.session.get("nama"),
        "role": request.session.get("role"),
        "kelas_id": request.session.get("kelas_id"),
    }


def require_role(*allowed_roles: str):
    def dependency(user: dict = Depends(require_login)) -> dict:
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user['role']}' tidak punya akses ke fitur ini.",
            )
        return user

    return dependency


def check_walas_scope(user: dict, kelas_id: uuid.UUID | None) -> None:
    if user["role"] != "walas":
        return
    try:
        assigned_class = uuid.UUID(str(user.get("kelas_id")))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun walas belum memiliki kelas yang valid.",
        ) from exc
    if kelas_id != assigned_class:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Walas hanya bisa mengakses data kelasnya sendiri.",
        )
