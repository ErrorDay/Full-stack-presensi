"""
main.py
Entry point aplikasi web Program Absensi (FastAPI + SQLAdmin).

Menggantikan App.py (PySide6) versi lama. Semua service Python
(recognition_service, anti_spoof_service, attendance_service, dst)
TIDAK diubah — hanya dipanggil dari sini / dari router di folder api/.
"""

import os
from contextlib import asynccontextmanager

# WAJIB diimpor sebelum modul lain yang menyentuh InsightFace,
# supaya tidak ikut menarik dependency torch yang bermasalah.
import modules._patch_torch_deps  # noqa: F401

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from database.connections import engine  # engine PostgreSQL, sudah ada dari project lama
from admin import setup_admin

from service.recognition_service import RecognitionService
from service.anti_spoof_service import AntiSpoofService
# from service.notification_service import start_scheduler, stop_scheduler
# ^ diaktifkan di tahap 5 (notifikasi & report otomatis)

from api import attendance, enrollment
from api import dashboard, classes, students, attendance_web, settings_web, export, library, auth_web
# ^ router baru (Opsi B) yang match kontrak frontend React (Emergent UI)

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY belum diset di .env — wajib ada untuk session login "
        "(admin panel & endpoint API). Tambahkan baris: SECRET_KEY=<string-acak-panjang>"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup / shutdown lifecycle.

    RecognitionService & AntiSpoofService dimuat SEKALI di sini dan
    disimpan di app.state — supaya model InsightFace/ONNX tidak
    di-load ulang tiap request (mahal). Ini setara dengan
    CameraThread.__init__() di tes_kamera.py, tapi hidup selama
    aplikasi web berjalan, bukan selama thread kamera terbuka.
    """

    print("[STARTUP] Memuat RecognitionService (InsightFace)...")
    app.state.recognition = RecognitionService()

    print("[STARTUP] Memuat AntiSpoofService (MiniFASNetV2 ONNX)...")
    app.state.anti_spoof = AntiSpoofService()

    # Cooldown tracker untuk endpoint /api/presensi/scan & /api/attendance/recognize
    # (dict: nama siswa -> timestamp scan terakhir)
    app.state.attendance_last_scan = {}
    app.state.library_last_scan = {}

    # start_scheduler()  # tahap 5
    print("[STARTUP] Program Absensi Web siap")

    yield

    # stop_scheduler()  # tahap 5
    print("[SHUTDOWN] Program Absensi Web dihentikan")


app = FastAPI(
    title="Program Absensi",
    description="Sistem absensi wajah offline berbasis web (FastAPI + SQLAdmin)",
    version="1.0.0",
    lifespan=lifespan,
)

# Session cookie — dipakai bersama oleh SQLAdmin login DAN endpoint API
# (lihat auth.py: AdminAuth + require_login membaca session yang sama).
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# CORS — dibutuhkan karena frontend React (npm start / build terpisah)
# berjalan di origin berbeda dari backend FastAPI ini saat development.
# PENTING: harus origin SPESIFIK (bukan "*"), karena browser MELARANG
# kombinasi wildcard + allow_credentials=True (dibutuhkan supaya session
# cookie login ikut terkirim). Isi CORS_ORIGINS di .env, pisahkan dengan
# koma kalau lebih dari satu (mis. http://localhost:3000,https://presensi.sekolah.sch.id).
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Folder untuk file statis (JS kamera, CSS, foto hasil enrollment, dll)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# Daftarkan SQLAdmin (CRUD Siswa, Kelas, Setting, dst) ke app ini — sekarang butuh login
setup_admin(app, engine, secret_key=SECRET_KEY)

# Router API milik kita sendiri (device operator / kios presensi terpisah)
app.include_router(attendance.router, prefix="/api/presensi", tags=["Presensi (device kita)"])
app.include_router(enrollment.router, prefix="/api/siswa", tags=["Enrollment (device kita)"])

# Router BARU (Opsi B) -- kontraknya PERSIS mengikuti frontend React (Emergent UI),
# jadi prefix-nya harus sama persis dengan yang dipanggil lib/api.js
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard (web)"])
app.include_router(classes.router, prefix="/api/classes", tags=["Kelas (web)"])
app.include_router(students.router, prefix="/api/students", tags=["Siswa (web)"])
app.include_router(attendance_web.router, prefix="/api/attendance", tags=["Presensi (web)"])
app.include_router(settings_web.router, prefix="/api/settings", tags=["Pengaturan (web)"])
app.include_router(export.router, prefix="/api/export", tags=["Ekspor (web)"])
app.include_router(library.router, prefix="/api/library", tags=["Perpustakaan (web)"])
app.include_router(auth_web.router, prefix="/api/auth", tags=["Autentikasi (web)"])
# app.include_router(report.router, prefix="/api/report", tags=["Laporan"])
# ^ diaktifkan di tahap 5


@app.get("/")
def root():
    """
    Redirect sederhana ke halaman admin, mirip routes/web.php di versi
    Laravel ('/' -> redirect('/admin')).
    """
    return {"message": "Program Absensi Web aktif. Buka /admin untuk dashboard."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
