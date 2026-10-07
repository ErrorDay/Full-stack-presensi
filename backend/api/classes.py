"""
api/classes.py
CRUD /classes + PATCH /classes/visibility -- dipanggil Kelas.jsx.

Proteksi role:
  GET (lihat)                    -> admin, operator, walas (walas cuma lihat kelasnya sendiri)
  POST/PUT/DELETE/PATCH (ubah)   -> admin saja
"""

from fastapi import APIRouter, HTTPException, Depends

from pydantic import BaseModel

from database.session import SessionLocal
from database.models import Kelas, Siswa
from api.grade_utils import tingkat_ke_grade, grade_ke_tingkat
from auth import require_role

router = APIRouter()


class ClassIn(BaseModel):
    name: str
    grade: int | str  # frontend kirim integer (10/11/12); dikonversi ke Romawi saat disimpan


class VisibilityIn(BaseModel):
    grade: int | str
    visible: bool


def _serialize(kelas: Kelas, db) -> dict:
    student_count = (
        db.query(Siswa)
        .filter(Siswa.kelas_id == kelas.id, Siswa.status == "AKTIF")
        .count()
    )
    return {
        "id": str(kelas.id),
        "name": kelas.nama,
        "grade": tingkat_ke_grade(kelas.tingkat),
        "visible": kelas.visible,
        "student_count": student_count,
    }


@router.get("")
def list_classes(user: dict = Depends(require_role("admin", "operator", "walas"))):
    db = SessionLocal()
    try:
        query = db.query(Kelas)

        if user["role"] == "walas":
            query = query.filter(Kelas.id == user["kelas_id"])

        classes = query.order_by(Kelas.tingkat, Kelas.nama).all()
        return [_serialize(k, db) for k in classes]
    finally:
        db.close()


@router.post("")
def create_class(data: ClassIn, user: dict = Depends(require_role("admin"))):
    db = SessionLocal()
    try:
        exists = db.query(Kelas).filter(Kelas.nama == data.name).first()
        if exists:
            raise HTTPException(400, "Nama kelas sudah ada")

        kelas = Kelas(
            nama=data.name,
            tingkat=grade_ke_tingkat(data.grade),
            jurusan="",
            tahun_ajaran="2026/2027",
            aktif=True,
            visible=True,
        )
        db.add(kelas)
        db.commit()
        db.refresh(kelas)
        return _serialize(kelas, db)
    finally:
        db.close()


@router.put("/{class_id}")
def update_class(class_id: int, data: ClassIn, user: dict = Depends(require_role("admin"))):
    db = SessionLocal()
    try:
        kelas = db.query(Kelas).filter(Kelas.id == class_id).first()
        if kelas is None:
            raise HTTPException(404, "Kelas tidak ditemukan")

        kelas.nama = data.name
        kelas.tingkat = grade_ke_tingkat(data.grade)
        db.commit()
        db.refresh(kelas)
        return _serialize(kelas, db)
    finally:
        db.close()


@router.delete("/{class_id}")
def delete_class(class_id: int, user: dict = Depends(require_role("admin"))):
    db = SessionLocal()
    try:
        n = db.query(Siswa).filter(Siswa.kelas_id == class_id).count()
        if n:
            raise HTTPException(400, f"Kelas masih memiliki {n} siswa. Pindahkan siswa terlebih dahulu.")

        kelas = db.query(Kelas).filter(Kelas.id == class_id).first()
        if kelas is None:
            raise HTTPException(404, "Kelas tidak ditemukan")

        db.delete(kelas)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@router.patch("/visibility")
def set_visibility(data: VisibilityIn, user: dict = Depends(require_role("admin"))):
    """Sembunyikan/tampilkan SEMUA kelas dalam satu tingkat sekaligus."""
    db = SessionLocal()
    try:
        tingkat = grade_ke_tingkat(data.grade)
        db.query(Kelas).filter(Kelas.tingkat == tingkat).update({"visible": data.visible})
        db.commit()
        return {"ok": True, "grade": data.grade, "visible": data.visible}
    finally:
        db.close()
