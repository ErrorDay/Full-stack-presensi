"""
api/attendance_web.py
GET/POST /attendance, POST /attendance/recognize, GET /attendance/recap/monthly
-- dipanggil Presensi.jsx.

Beda dari api/attendance.py (endpoint /api/presensi/scan yang sudah
ada sebelumnya untuk device operator kita sendiri): file ini
menyediakan kontrak PERSIS yang diharapkan frontend React (Opsi B),
termasuk mode simulasi (student_id langsung, tanpa gambar) dan
override status manual (dipakai walas untuk set "Izin").

Sesuai keputusan login: endpoint di sini BELUM diproteksi require_login
("sambungkan dulu tanpa login, tambah belakangan").
"""

from datetime import datetime, date as date_cls
import time
import uuid

# WAJIB diimpor sebelum modul lain yang menyentuh InsightFace.
import modules._patch_torch_deps  # noqa: F401

from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import extract

from database.session import SessionLocal
from database.models import Siswa, Kelas, Absensi
from service.attendance_service import AttendanceService, STATUS_LIST
from service.library_service import LibraryService
from service.report_service import ReportService
from api.utils import decode_base64_image

router = APIRouter()

COOLDOWN_DETIK = 10  # sama seperti api/attendance.py -- cegah 1 siswa tercatat berkali-kali beruntun


class AttendanceIn(BaseModel):
    student_id: uuid.UUID
    status: str | None = None  # None -> otomatis; diisi -> override manual (mis. "Izin")
    date: str | None = None
    time: str | None = None


class RecognizeIn(BaseModel):
    image_base64: str | None = None
    student_id: uuid.UUID | None = None  # mode simulasi, tanpa kamera
    target: str = "attendance"  # "attendance" (default) atau "library" (kunjungan perpustakaan)


def _serialize(a: Absensi, siswa: Siswa, kelas: Kelas | None) -> dict:
    return {
        "id": str(a.id),
        "student_id": str(a.student_id),
        "nisn": siswa.nisn,
        "name": siswa.name,
        "class_id": str(siswa.class_id) if siswa.class_id else None,
        "class_name": kelas.name if kelas else "",
        "date": a.attendance_date.isoformat(),
        "time": a.checked_at.astimezone().strftime("%H:%M:%S"),
        "status": a.status,
    }


def _serialize_visit(k, siswa: Siswa, kelas: Kelas | None, visit_ke: int) -> dict:
    return {
        "id": str(k.id),
        "student_id": str(siswa.id),
        "nisn": siswa.nisn,
        "name": siswa.name,
        "class_id": str(siswa.class_id) if siswa.class_id else None,
        "class_name": kelas.name if kelas else "",
        "date": k.visited_at.astimezone().date().isoformat(),
        "time": k.visited_at.astimezone().strftime("%H:%M:%S"),
        "visit_ke": visit_ke,
    }


@router.post("")
def create_attendance(data: AttendanceIn, request: Request):
    """Input manual -- dipakai walas untuk set status (mis. Izin)."""

    if data.status and data.status not in STATUS_LIST:
        raise HTTPException(400, "Status tidak valid")

    db = SessionLocal()
    attendance = AttendanceService()
    try:
        siswa = db.query(Siswa).filter(Siswa.id == data.student_id).first()
        if siswa is None:
            raise HTTPException(404, "Siswa tidak ditemukan")

        tanggal = date_cls.fromisoformat(data.date) if data.date else None
        waktu = datetime.strptime(data.time, "%H:%M:%S").time() if data.time else None

        user_id = request.session.get("user_id")
        try:
            created_by = uuid.UUID(str(user_id)) if user_id else None
        except ValueError as exc:
            raise HTTPException(401, "ID pengguna pada sesi tidak valid") from exc
        absensi, updated = attendance.record_attendance(
            siswa,
            data.status,
            tanggal,
            waktu,
            created_by=created_by,
            source="manual",
        )
        kelas = (
            db.query(Kelas).filter(Kelas.id == siswa.class_id).first()
            if siswa.class_id
            else None
        )

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
):
    db = SessionLocal()
    try:
        query = (
            db.query(Absensi, Siswa, Kelas)
            .join(Siswa, Absensi.student_id == Siswa.id)
            .outerjoin(Kelas, Siswa.class_id == Kelas.id)
        )

        if date:
            query = query.filter(Absensi.attendance_date == date_cls.fromisoformat(date))
        elif year and month:
            query = query.filter(
                extract("year", Absensi.attendance_date) == year,
                extract("month", Absensi.attendance_date) == month,
            )
        elif year:
            query = query.filter(extract("year", Absensi.attendance_date) == year)

        if jam:
            query = query.filter(extract("hour", Absensi.checked_at) == int(jam))
        if class_id:
            try:
                parsed_class_id = uuid.UUID(class_id)
            except ValueError as exc:
                raise HTTPException(422, "class_id harus UUID yang valid") from exc
            query = query.filter(Siswa.class_id == parsed_class_id)
        if status:
            query = query.filter(Absensi.status == status)

        rows = query.order_by(
            Absensi.attendance_date.desc(), Absensi.checked_at.desc()
        ).limit(10000).all()
        return [_serialize(a, s, k) for a, s, k in rows]
    finally:
        db.close()


@router.post("/recognize")
def recognize(data: RecognizeIn, request: Request):
    """
    Titik integrasi kamera -- setara POST /api/attendance/recognize
    di server.py Emergent, tapi recognition-nya jalan langsung di
    proses FastAPI ini (RecognitionService + AntiSpoofService dari
    app.state), bukan lewat face_recognition_bridge.py terpisah.

    target="attendance" (default) -> catat ke tabel Absensi (1x/hari, upsert)
    target="library" -> catat ke tabel Kunjungan (boleh berkali-kali/hari, selalu insert baru)
    """

    is_library = data.target == "library"

    db = SessionLocal()
    attendance = AttendanceService()
    library = LibraryService()

    try:
        # ---- mode simulasi: langsung catat tanpa gambar ----
        if data.student_id:
            siswa = db.query(Siswa).filter(Siswa.id == data.student_id).first()
            if siswa is None:
                raise HTTPException(404, "Siswa tidak ditemukan")
            kelas = (
                db.query(Kelas).filter(Kelas.id == siswa.class_id).first()
                if siswa.class_id
                else None
            )

            if is_library:
                kunjungan, visit_ke = library.record_visit(
                    siswa, created_by=_session_user_id(request), source="manual"
                )
                return {
                    "recognized": True,
                    "mode": "simulasi",
                    "visit": _serialize_visit(kunjungan, siswa, kelas, visit_ke),
                }

            absensi, updated = attendance.process_attendance(
                siswa, created_by=_session_user_id(request)
            )
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

        # cooldown terpisah untuk presensi vs perpustakaan -- supaya siswa
        # yang baru absen tetap bisa langsung discan di mode perpustakaan
        # tanpa nunggu cooldown presensi selesai, dan sebaliknya.
        last_scan = (
            request.app.state.library_last_scan
            if is_library
            else request.app.state.attendance_last_scan
        )

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
        kelas = (
            db.query(Kelas).filter(Kelas.id == siswa.class_id).first()
            if siswa.class_id
            else None
        )
        nama = siswa.name.strip()
        sekarang = time.time()

        if is_library:
            if nama in last_scan and sekarang - last_scan[nama] < COOLDOWN_DETIK:
                return {"recognized": False, "message": f"{siswa.name} baru saja tercatat, tunggu beberapa detik."}

            kunjungan, visit_ke = library.record_visit(
                siswa, created_by=_session_user_id(request), source="face"
            )
            last_scan[nama] = sekarang
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
                .filter(
                    Absensi.student_id == siswa.id,
                    Absensi.attendance_date == date_cls.today(),
                )
                .first()
            )
            return {
                "recognized": True,
                "mode": "face_recognition",
                "record": _serialize(absensi_hari_ini, siswa, kelas) if absensi_hari_ini else None,
                "updated": False,
                "cooldown": True,
            }

        absensi, updated = attendance.process_attendance(
            siswa, created_by=_session_user_id(request)
        )
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
def recap_monthly(year: int = Query(...), month: int = Query(...), class_id: str | None = None):
    report = ReportService()
    try:
        from modules.kalender import is_hari_sekolah
        import calendar as _cal

        days_in_month = _cal.monthrange(year, month)[1]
        hari_sekolah_count = sum(
            1 for d in range(1, days_in_month + 1)
            if is_hari_sekolah(date_cls(year, month, d))
        )

        try:
            parsed_class_id = uuid.UUID(class_id) if class_id else None
        except ValueError as exc:
            raise HTTPException(422, "class_id harus UUID yang valid") from exc
        rows = report.get_rekap_bulanan(year, month, parsed_class_id)
        return {"year": year, "month": month, "hari_sekolah": hari_sekolah_count, "rows": rows}
    finally:
        report.close()


def _session_user_id(request: Request) -> uuid.UUID | None:
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    try:
        return uuid.UUID(str(user_id))
    except (TypeError, ValueError) as exc:
        raise HTTPException(401, "ID pengguna pada sesi tidak valid") from exc
