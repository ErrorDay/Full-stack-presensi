"""
api/auth_web.py
POST /login, POST /logout, GET /me -- dipakai frontend React untuk
autentikasi. Session cookie yang dipakai SAMA dengan yang dipakai
AdminAuth (SQLAdmin /admin) dan require_login/require_role di endpoint
lain -- jadi kalau seseorang sudah login lewat sini, otomatis juga
"login" untuk endpoint API manapun yang dia berwenang akses.
"""

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from auth import _authenticate_user

router = APIRouter()


class LoginIn(BaseModel):
    username: str
    password: str


def _session_payload(request: Request) -> dict:
    return {
        "username": request.session["username"],
        "nama": request.session.get("nama"),
        "role": request.session["role"],
        "kelas_id": request.session.get("kelas_id"),
    }


@router.post("/login")
def login(data: LoginIn, request: Request):
    user = _authenticate_user(data.username, data.password)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau password salah.",
        )

    request.session.update({
        "user_id": user.id,
        "username": user.username,
        "nama": user.nama,
        "role": user.role,
        "kelas_id": getattr(user, "kelas_id", None),
    })

    return _session_payload(request)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    """
    Dipanggil frontend saat pertama load (mis. setelah refresh halaman)
    untuk cek apakah masih ada sesi login yang aktif.
    """
    if "user_id" not in request.session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Belum login.",
        )

    return _session_payload(request)
