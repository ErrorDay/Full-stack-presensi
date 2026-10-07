"""
api/students.py
CRUD /students + POST /students/{id}/migrate + POST /students/assign-bulk
+ POST /students/bulk-status + POST /students/bulk-status-angkatan
+ POST /students/set-angkatan -- dipanggil Kelas.jsx & Siswa.jsx.

Proteksi role:
  GET (lihat)                              -> admin, operator, walas (walas cuma lihat kelasnya sendiri)
  POST/PUT/DELETE/migrate/assign-bulk/dll  -> admin saja
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from database.session import SessionLocal
from database.models import Siswa, Kelas
from api.grade_utils import tingkat_ke_grade
from auth import require_role

router = APIRouter()


class StudentIn(BaseModel):
    nisn: str
    name: str
    gender: str = "L"
    class_id: str
    status: str = "AKTIF"
    angkatan: str | None = None


class MigrateIn(BaseModel):
    class_id: str


class AssignBulkIn(BaseModel):
    class_id: str
    student_ids: list[str]


class BulkStatusIn(BaseModel):
    class_id: str
    status: str  # "AKTIF" atau "NONAKTIF"


class BulkStatusAngkatanIn(BaseModel):
    angkatan: str
    status: str  # "AKTIF" atau "NONAKTIF"


class SetAngkatanIn(BaseModel):
    class_id: str
    angkatan: str


def _serialize(siswa: Siswa, kelas: Kelas | None = None) -> dict:
    kelas = kelas or siswa.kelas
    return {
        "id": str(siswa.id),
        "nisn": siswa.nis or "",
        "name": siswa.nama,
        "gender": siswa.jenis_kelamin or "L",
        "class_id": str(siswa.kelas_id),
        "class_name": kelas.nama if kelas else "",
        "grade": tingkat_ke_grade(kelas.tingkat) if kelas else "",
        "status": siswa.status,
        "angkatan": siswa.angkatan or "",
    }


@router.get("")
def list_students(
    class_id: str | None = None,
    angkatan: str | None = None,
    q: str | None = None,
    status: str | None = "AKTIF",
    # ^ default cuma tampilkan yang AKTIF (angkatan yang sudah lulus/
    # dinonaktifkan otomatis tersembunyi dari frontend). Kirim
    # status=NONAKTIF untuk lihat alumni, atau status=semua untuk lihat semuanya.
    user: dict = Depends(require_role("admin", "operator", "walas")),
):
    db = SessionLocal()
    try:
        query = db.query(Siswa)

        if user["role"] == "walas":
            # walas cuma boleh lihat siswa di kelasnya, apapun class_id
            # yang diminta di query param -- dipaksa timpa.
            query = query.filter(Siswa.kelas_id == user["kelas_id"])
        elif class_id:
            query = query.filter(Siswa.kelas_id == int(class_id))

        if angkatan:
            query = query.filter(Siswa.angkatan == angkatan)

        if status and status.lower() != "semua":
            query = query.filter(Siswa.status == status)

        if q:
            query = query.filter(Siswa.nama.ilike(f"%{q}%"))

        siswa_list = query.order_by(Siswa.nama).all()
        return [_serialize(s) for s in siswa_list]
    finally:
        db.close()


@router.post("")
def create_student(data: StudentIn, user: dict = Depends(require_role("admin"))):
    db = SessionLocal()
    try:
        kelas = db.query(Kelas).filter(Kelas.id == int(data.class_id)).first()
        if kelas is None:
            raise HTTPException(404, "Kelas tidak ditemukan")

        if data.nisn and db.query(Siswa).filter(Siswa.nis == data.nisn).first():
            raise HTTPException(400, "NIS/NISN sudah terdaftar")

        siswa = Siswa(
            nis=data.nisn or None,
            nama=data.name,
            kelas_id=kelas.id,
            jenis_kelamin=data.gender,
            status=data.status,
            angkatan=data.angkatan or None,
        )
        db.add(siswa)
        db.commit()
        db.refresh(siswa)
        return _serialize(siswa, kelas)
    finally:
        db.close()


@router.post("/assign-bulk")
def assign_students_bulk(data: AssignBulkIn, user: dict = Depends(require_role("admin"))):
    """
    Masukkan banyak siswa YANG SUDAH TERDAFTAR ke satu kelas sekaligus
    (dipakai Kelas.jsx saat admin pilih dari daftar siswa existing,
    beda dari POST /students yang untuk siswa benar-benar baru).
    """
    db = SessionLocal()
    try:
        kelas = db.query(Kelas).filter(Kelas.id == int(data.class_id)).first()
        if kelas is None:
            raise HTTPException(404, "Kelas tidak ditemukan")

        ids = [int(sid) for sid in data.student_ids]
        moved = (
            db.query(Siswa)
            .filter(Siswa.id.in_(ids))
            .update({"kelas_id": kelas.id}, synchronize_session=False)
        )
        db.commit()

        return {"ok": True, "moved": moved, "class_id": str(kelas.id)}
    finally:
        db.close()


@router.post("/set-angkatan")
def set_angkatan(data: SetAngkatanIn, user: dict = Depends(require_role("admin"))):
    """
    Tandai SEMUA siswa dalam satu kelas dengan angkatan tertentu sekaligus
    -- dipakai sekali per kelas (mis. setelah seeding kelas baru), karena
    angkatan tidak lagi dibaca dari struktur folder dataset/ (yang tetap
    per kelas/jurusan seperti biasa).
    """
    db = SessionLocal()
    try:
        kelas = db.query(Kelas).filter(Kelas.id == int(data.class_id)).first()
        if kelas is None:
            raise HTTPException(404, "Kelas tidak ditemukan")

        jumlah = (
            db.query(Siswa)
            .filter(Siswa.kelas_id == kelas.id)
            .update({"angkatan": data.angkatan}, synchronize_session=False)
        )
        db.commit()

        return {"ok": True, "jumlah": jumlah, "class_id": str(kelas.id), "angkatan": data.angkatan}
    finally:
        db.close()


@router.post("/bulk-status")
def bulk_status(data: BulkStatusIn, request: Request, user: dict = Depends(require_role("admin"))):
    """
    Ubah status SEMUA siswa dalam satu KELAS sekaligus.
    Untuk nonaktifkan berdasarkan ANGKATAN (lintas kelas), pakai
    /students/bulk-status-angkatan sebagai gantinya.
    """
    if data.status not in ("AKTIF", "NONAKTIF"):
        raise HTTPException(400, "status harus AKTIF atau NONAKTIF")

    db = SessionLocal()
    try:
        kelas = db.query(Kelas).filter(Kelas.id == int(data.class_id)).first()
        if kelas is None:
            raise HTTPException(404, "Kelas tidak ditemukan")

        jumlah = (
            db.query(Siswa)
            .filter(Siswa.kelas_id == kelas.id)
            .update({"status": data.status}, synchronize_session=False)
        )
        db.commit()

        request.app.state.recognition.reload_embeddings()

        return {"ok": True, "jumlah": jumlah, "class_id": str(kelas.id), "status": data.status}
    finally:
        db.close()


@router.post("/bulk-status-angkatan")
def bulk_status_angkatan(data: BulkStatusAngkatanIn, request: Request, user: dict = Depends(require_role("admin"))):
    """
    Ubah status SEMUA siswa dalam satu ANGKATAN sekaligus -- dipakai saat
    angkatan lulus, TIDAK PEDULI mereka sekarang tersebar di kelas mana
    (termasuk yang sudah di-reshuffle/migrasi kelas). Ini alasan utama
    kolom angkatan dipisah dari kelas_id.

    Embedding wajah & data siswa TIDAK dihapus -- cuma disembunyikan
    dari listing (status != AKTIF) dan dari recognition.
    """
    if data.status not in ("AKTIF", "NONAKTIF"):
        raise HTTPException(400, "status harus AKTIF atau NONAKTIF")

    db = SessionLocal()
    try:
        jumlah = (
            db.query(Siswa)
            .filter(Siswa.angkatan == data.angkatan)
            .update({"status": data.status}, synchronize_session=False)
        )
        db.commit()

        request.app.state.recognition.reload_embeddings()

        return {"ok": True, "jumlah": jumlah, "angkatan": data.angkatan, "status": data.status}
    finally:
        db.close()


@router.put("/{student_id}")
def update_student(student_id: int, data: StudentIn, request: Request, user: dict = Depends(require_role("admin"))):
    db = SessionLocal()
    try:
        kelas = db.query(Kelas).filter(Kelas.id == int(data.class_id)).first()
        if kelas is None:
            raise HTTPException(404, "Kelas tidak ditemukan")

        siswa = db.query(Siswa).filter(Siswa.id == student_id).first()
        if siswa is None:
            raise HTTPException(404, "Siswa tidak ditemukan")

        status_berubah = siswa.status != data.status

        siswa.nis = data.nisn or None
        siswa.nama = data.name
        siswa.kelas_id = kelas.id
        siswa.jenis_kelamin = data.gender
        siswa.status = data.status
        siswa.angkatan = data.angkatan or None
        db.commit()
        db.refresh(siswa)

        if status_berubah:
            request.app.state.recognition.reload_embeddings()

        return _serialize(siswa, kelas)
    finally:
        db.close()


@router.delete("/{student_id}")
def delete_student(student_id: int, user: dict = Depends(require_role("admin"))):
    db = SessionLocal()
    try:
        siswa = db.query(Siswa).filter(Siswa.id == student_id).first()
        if siswa is None:
            raise HTTPException(404, "Siswa tidak ditemukan")
        db.delete(siswa)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@router.post("/{student_id}/migrate")
def migrate_student(student_id: int, data: MigrateIn, user: dict = Depends(require_role("admin"))):
    db = SessionLocal()
    try:
        kelas = db.query(Kelas).filter(Kelas.id == int(data.class_id)).first()
        if kelas is None:
            raise HTTPException(404, "Kelas tujuan tidak ditemukan")

        siswa = db.query(Siswa).filter(Siswa.id == student_id).first()
        if siswa is None:
            raise HTTPException(404, "Siswa tidak ditemukan")

        siswa.kelas_id = kelas.id
        db.commit()
        db.refresh(siswa)
        return _serialize(siswa, kelas)
    finally:
        db.close()
