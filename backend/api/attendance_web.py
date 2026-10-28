"""
api/attendance_web.py
GET/POST /attendance, POST /attendance/recognize, GET /attendance/recap/monthly
-- dipanggil Presensi.jsx.

Beda dari api/attendance.py (endpoint /api/presensi/scan yang sudah
ada sebelumnya untuk device operator kita sendiri): file ini
menyediakan kontrak PERSIS yang diharapkan frontend React (Opsi B),
termasuk mode simulasi (student_id langsung, tanpa gambar) dan
override status manual (dipakai walas untuk set "Izin").

Proteksi akses: semua endpoint membutuhkan sesi login; operator/admin dapat
memindai dan mengelola presensi, sedangkan walas hanya dapat melihat atau
mengubah presensi siswa di kelasnya sendiri.
"""

from datetime import datetime, date as date_cls
import time

# WAJIB diimpor sebelum modul lain yang menyentuh InsightFace.
import modules._patch_torch_deps  # noqa: F401

from fastapi import APIRouter, Request, HTTPException, Query, Depends
from pydantic import BaseModel
from sqlalchemy import extract

from database.session import SessionLocal
from database.models import Siswa, Kelas, Absensi
from service.attendance_service import AttendanceService, STATUS_LIST
from service.library_service import LibraryService
from service.report_service import ReportService
from api.utils import decode_base64_image
from auth import require_role, check_walas_scope

router = APIRouter()

COOLDOWN_DETIK = 10  # sama seperti api/attendance.py -- cegah 1 siswa tercatat berkali-kali beruntun


class AttendanceIn(BaseModel):
    student_id: str
    status: str | None = None  # None -> otomatis; diisi -> override manual (mis. "Izin")
    date: str | None = None
    time: str | None = None


class RecognizeIn(BaseModel):
    image_base64: str | None = None
    student_id: str | None = None  # mode simulasi, tanpa kamera
    target: str = "attendance"  # "attendance" (default) atau "library" (kunjungan perpustakaan)


def _serialize(a: Absensi, siswa: Siswa, kelas: Kelas) -> dict:
    return {
        "id": str(a.id),
        "student_id": str(a.siswa_id),
        "nisn": siswa.nis or "",
        "name": siswa.nama,
        "class_id": str(siswa.kelas_id),
        "class_name": kelas.nama if kelas else "",
        "date": a.tanggal.isoformat(),
        "time": a.jam_masuk.strftime("%H:%M:%S"),
        "status": a.status,
    }


def _serialize_visit(k, siswa: Siswa, kelas: Kelas, visit_ke: int) -> dict:
    return {
        "id": str(k.id),
        "student_id": str(siswa.id),
        "nisn": siswa.nis or "",
        "name": siswa.nama,
        "class_id": str(siswa.kelas_id),
        "class_name": kelas.nama if kelas else "",
        "date": k.tanggal.isoformat(),
        "time": k.waktu.strftime("%H:%M:%S"),
        "visit_ke": visit_ke,
    }


@router.post("")
def create_attendance(
    data: AttendanceIn,
    user: dict = Depends(require_role("admin", "operator", "walas")),
):
    """Input manual -- dipakai walas untuk set status (mis. Izin)."""

    if data.status and data.status not in STATUS_LIST:
        raise HTTPException(400, "Status tidak valid")

    db = SessionLocal()
    attendance = AttendanceService()
    try:
        siswa = db.query(Siswa).filter(Siswa.id == int(data.student_id)).first()
        if siswa is None:
            raise HTTPException(404, "Siswa tidak ditemukan")
        check_walas_scope(user, siswa.kelas_id)

        tanggal = date_cls.fromisoformat(data.date) if data.date else None
        waktu = datetime.strptime(data.time, "%H:%M:%S").time() if data.time else None

        absensi, updated = attendance.record_attendance(siswa, data.status, tanggal, waktu)
        kelas = db.query(Kelas).filter(Kelas.id == siswa.kelas_id).first()

        return {"record": _serialize(absensi, siswa, kelas), "updated": updated}
    finally:
        db.close()
        attendance.close()


@router.get("")
def list_attendance(
    date: str | None = None,
    year: int | None = None,
    jam: str | None = None,
    class_id: str | None = None,
    status: str | None = None,
    month: int | None = None,
    user: dict = Depends(require_role("admin", "operator", "walas")),
):
    db = SessionLocal()
    try:
        query = (
            db.query(Absensi, Siswa, Kelas)
            .join(Siswa, Absensi.siswa_id == Siswa.id)
            .join(Kelas, Siswa.kelas_id == Kelas.id)
        )

        if date:
            query = query.filter(Absensi.tanggal == date_cls.fromisoformat(date))
        elif year and month:
            query = query.filter(
                extract("year", Absensi.tanggal) == year,
                extract("month", Absensi.tanggal) == month,
            )
        elif year:
            query = query.filter(extract("year", Absensi.tanggal) == year)

        if jam:
            query = query.filter(Absensi.jam_masuk >= f"{jam.zfill(2)}:00:00", Absensi.jam_masuk < f"{jam.zfill(2)}:59:59")
        if user["role"] == "walas":
            query = query.filter(Siswa.kelas_id == user["kelas_id"])
        elif class_id:
            query = query.filter(Siswa.kelas_id == int(class_id))
        if status:
            query = query.filter(Absensi.status == status)

        rows = query.order_by(Absensi.tanggal.desc(), Absensi.jam_masuk.desc()).limit(10000).all()
        return [_serialize(a, s, k) for a, s, k in rows]
    finally:
        db.close()


@router.post("/recognize")
def recognize(
    data: RecognizeIn,
    request: Request,
    user: dict = Depends(require_role("admin", "operator")),
):
    """
    Titik integrasi kamera -- setara POST /api/attendance/recognize
    di server.py Emergent, tapi recognition-nya jalan langsung di
    proses FastAPI ini (RecognitionService + AntiSpoofService dari
    app.state), bukan lewat face_recognition_bridge.py terpisah.

    target="attendance" (default) -> catat ke tabel Absensi (1x/hari)
    target="library" -> catat ke tabel Kunjungan (cooldown satu jam per siswa)
    """

    is_library = data.target == "library"

    db = SessionLocal()
    attendance = AttendanceService()
    library = LibraryService()

    try:
        # ---- mode simulasi: langsung catat tanpa gambar ----
        if data.student_id:
            siswa = db.query(Siswa).filter(Siswa.id == int(data.student_id)).first()
            if siswa is None:
                raise HTTPException(404, "Siswa tidak ditemukan")
            kelas = db.query(Kelas).filter(Kelas.id == siswa.kelas_id).first()

            if is_library:
                kunjungan, visit_ke = library.record_visit(siswa)
                if kunjungan is None:
                    return {
                        "recognized": True,
                        "mode": "simulasi",
                        "cooldown": True,
                        "message": "Siswa baru saja berkunjung, cooldown berlaku selama satu jam.",
                    }
                return {
                    "recognized": True,
                    "mode": "simulasi",
                    "visit": _serialize_visit(kunjungan, siswa, kelas, visit_ke),
                }

            absensi, updated = attendance.process_attendance(siswa)
            return {
                "recognized": True,
                "mode": "simulasi",
                "record": _serialize(absensi, siswa, kelas),
                "updated": updated,
            }

        if not data.image_base64:
            raise HTTPException(400, "image_base64 diperlukan")

        # ---- mode kamera sungguhan ----
        try:
            frame = decode_base64_image(data.image_base64)
        except ValueError as e:
            raise HTTPException(400, str(e))

        recognizer = request.app.state.recognition
        anti_spoof = request.app.state.anti_spoof

        # Cooldown presensi singkat hanya membantu mengurangi pemrosesan
        # berulang; batas satu kali per hari dijaga oleh AttendanceService.
        last_scan = request.app.state.attendance_last_scan

        hasil = recognizer.recognize(frame)
        faces = [f for f in hasil["faces"] if f["siswa"] is not None]

        if not faces:
            return {"recognized": False, "message": "Wajah tidak dikenali atau tidak terdeteksi."}

        # ambil hasil dengan similarity tertinggi (sudah terurut oleh recognize())
        wajah = faces[0]
        siswa_hasil = wajah["siswa"]

        is_real, spoof_score = anti_spoof.is_real(frame, wajah["bbox"])
        if not is_real:
            return {"recognized": False, "message": "Terdeteksi sebagai foto/spoof, bukan wajah asli."}

        siswa = db.query(Siswa).filter(Siswa.id == siswa_hasil.id).first()
        kelas = db.query(Kelas).filter(Kelas.id == siswa.kelas_id).first()
        nama = siswa.nama.strip()
        sekarang = time.time()

        if is_library:
            kunjungan, visit_ke = library.record_visit(siswa)
            if kunjungan is None:
                return {
                    "recognized": True,
                    "mode": "face_recognition",
                    "cooldown": True,
                    "message": f"{siswa.nama} baru saja berkunjung, cooldown berlaku selama satu jam.",
                }
            return {
                "recognized": True,
                "mode": "face_recognition",
                "visit": _serialize_visit(kunjungan, siswa, kelas, visit_ke),
            }

        # --- COOLDOWN presensi: kalau siswa ini baru saja tercatat < 10 detik lalu,
        # jangan proses ulang (cegah 1x berdiri di depan kamera = tercatat berkali-kali) ---
        if nama in last_scan and sekarang - last_scan[nama] < COOLDOWN_DETIK:
            absensi_hari_ini = (
                db.query(Absensi)
                .filter(Absensi.siswa_id == siswa.id, Absensi.tanggal == date_cls.today())
                .first()
            )
            return {
                "recognized": True,
                "mode": "face_recognition",
                "record": _serialize(absensi_hari_ini, siswa, kelas) if absensi_hari_ini else None,
                "updated": False,
                "cooldown": True,
            }

        absensi, updated = attendance.process_attendance(siswa)
        last_scan[nama] = sekarang

        return {
            "recognized": True,
            "mode": "face_recognition",
            "record": _serialize(absensi, siswa, kelas),
            "updated": updated,
            "cooldown": False,
        }

    finally:
        db.close()
        attendance.close()
        library.close()


@router.get("/recap/monthly")
def recap_monthly(
    year: int = Query(...),
    month: int = Query(...),
    class_id: str | None = None,
    user: dict = Depends(require_role("admin", "operator", "walas")),
):
    report = ReportService()
    db = SessionLocal()
    try:
        from modules.kalender import is_hari_sekolah
        import calendar as _cal

        days_in_month = _cal.monthrange(year, month)[1]
        hari_sekolah_count = sum(
            1 for d in range(1, days_in_month + 1)
            if is_hari_sekolah(date_cls(year, month, d))
        )

        kelas_nama = None
        if user["role"] == "walas":
            if user["kelas_id"] is None:
                raise HTTPException(403, "Walas belum terhubung ke kelas.")
            kelas = db.query(Kelas).filter(Kelas.id == user["kelas_id"]).first()
            if kelas is None:
                raise HTTPException(403, "Kelas walas tidak ditemukan.")
            kelas_nama = kelas.nama
        elif class_id:
            kelas = db.query(Kelas).filter(Kelas.id == int(class_id)).first()
            kelas_nama = kelas.nama if kelas else None

        rows = report.get_rekap_bulanan(year, month, kelas_nama)
        return {"year": year, "month": month, "hari_sekolah": hari_sekolah_count, "rows": rows}
    finally:
        db.close()
        report.close()
