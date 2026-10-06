"""
auth.py
Fondasi autentikasi — dipakai bersama oleh:
1. SQLAdmin panel (/admin) via AdminAuth
2. Endpoint API via dependency require_login() / require_role()

Keduanya membaca session cookie yang SAMA, jadi siapapun (admin,
operator, walas) cukup login sekali di halaman login untuk mengakses
admin panel maupun endpoint API sesuai wewenangnya.

Pakai tabel User yang sudah ada di database/models.py
(username, password_hash, nama, role, aktif, kelas_id).

3 role yang didukung:
  - admin    : akses penuh ke semua fitur
  - operator : Dashboard + scan kamera (presensi & perpustakaan) + export laporan
  - walas    : Dashboard + lihat Kelas&Siswa + override status "Izin",
               SEMUANYA di-scope hanya untuk kelas yang tercatat di
               User.kelas_id (lihat check_walas_scope di bawah)
"""

from passlib.context import CryptContext
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from fastapi import Depends, HTTPException, status

from database.session import SessionLocal
from database.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ROLES = ["admin", "operator", "walas"]


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _authenticate_user(username: str, password: str) -> User | None:
    db = SessionLocal()
    try:
        user = (
            db.query(User)
            .filter(User.username == username, User.aktif.is_(True))
            .first()
        )

        if user is None:
            return None

        if not verify_password(password, user.password_hash):
            return None

        return user

    finally:
        db.close()


class AdminAuth(AuthenticationBackend):
    """
    Backend login untuk SQLAdmin panel (/admin).
    SQLAdmin otomatis menampilkan form login bawaan kalau backend ini
    didaftarkan ke Admin(...) di admin.py.
    """

    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

        user = _authenticate_user(username, password)

        if user is None:
            return False

        # Simpan identitas di session -- dipakai juga oleh
        # require_login()/require_role() di bawah untuk melindungi
        # endpoint API. kelas_id ikut disimpan supaya scoping walas
        # tidak perlu query database ulang di tiap request.
        request.session.update({
            "user_id": user.id,
            "username": user.username,
            "nama": user.nama,
            "role": user.role,
            # Database users lama belum memiliki kolom kelas_id. Ambil
            # secara opsional agar login tetap berjalan untuk semua skema.
            "kelas_id": getattr(user, "kelas_id", None),
        })
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return "user_id" in request.session


def require_login(request: Request) -> dict:
    """
    Dependency FastAPI dasar -- cuma cek sudah login atau belum,
    tanpa peduli role. Pakai require_role(...) kalau endpoint perlu
    dibatasi ke role tertentu.
    """

    if "user_id" not in request.session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Belum login. Silakan login terlebih dahulu.",
        )

    return {
        "user_id": request.session["user_id"],
        "username": request.session["username"],
        "nama": request.session.get("nama"),
        "role": request.session.get("role"),
        "kelas_id": request.session.get("kelas_id"),
    }


def require_role(*allowed_roles: str):
    """
    Dependency FACTORY -- pakai di endpoint yang cuma boleh diakses
    role tertentu.

    Contoh:
        @router.post("")
        def create_class(data: ClassIn, user: dict = Depends(require_role("admin"))):
            ...

        @router.get("")
        def list_classes(user: dict = Depends(require_role("admin", "operator", "walas"))):
            ...
    """

    def dependency(user: dict = Depends(require_login)) -> dict:
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user['role']}' tidak punya akses ke fitur ini.",
            )
        return user

    return dependency


def check_walas_scope(user: dict, kelas_id: int) -> None:
    """
    Dipanggil MANUAL di dalam endpoint (bukan dependency) untuk kasus
    yang butuh cek kelas_id dari BODY request, bukan dari path/query
    saja -- mis. POST /attendance (override status) harus cek kelas_id
    milik SISWA yang statusnya mau diubah, baru bisa tahu setelah
    query siswa dulu.

    Raise 403 kalau user role="walas" dan kelas_id yang diminta BUKAN
    kelasnya sendiri. Admin & operator selalu lolos (tidak di-scope).
    """
    if user["role"] == "walas" and user.get("kelas_id") != kelas_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Walas hanya bisa mengakses data kelasnya sendiri.",
        )
