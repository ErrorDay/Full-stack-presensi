"""
api/classes.py
CRUD /classes + PATCH /classes/visibility -- dipanggil Kelas.jsx.

Proteksi role:
  GET (lihat)                    -> admin, operator, walas (walas cuma lihat kelasnya sendiri)
  POST/PUT/DELETE/PATCH (ubah)   -> admin saja
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database.session import SessionLocal
from database.models import Kelas, Siswa
from auth import require_role

router = APIRouter()

ROMAN_TO_GRADE = {"X": 10, "XI": 11, "XII": 12}
GRADE_TO_ROMAN = {value: key for key, value in ROMAN_TO_GRADE.items()}


class ClassIn(BaseModel):
    name: str
    grade: int | str


class VisibilityIn(BaseModel):
    grade: int | str
    visible: bool


def _parse_grade(value: int | str) -> int:
    if isinstance(value, str):
        value = ROMAN_TO_GRADE.get(value.strip().upper(), value.strip())
    try:
        grade = int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, "Grade harus 10, 11, 12, X, XI, atau XII") from exc
    if grade not in GRADE_TO_ROMAN:
        raise HTTPException(422, "Grade harus 10, 11, atau 12")
    return grade


def _serialize(kelas: Kelas, db) -> dict:
    student_count = (
        db.query(Siswa)
        .filter(Siswa.class_id == kelas.id, Siswa.status == "Aktif")
        .count()
    )
    return {
        "id": str(kelas.id),
        "name": kelas.name,
        "grade": kelas.grade,
        "grade_roman": GRADE_TO_ROMAN[kelas.grade],
        "visible": kelas.visible,
        "student_count": student_count,
    }


@router.get("")
def list_classes(user: dict = Depends(require_role("admin", "operator", "walas"))):
    db = SessionLocal()
    try:
        query = db.query(Kelas)

        if user["role"] == "walas":
            class_id = user.get("kelas_id")
            if not class_id:
                return []
            query = query.filter(Kelas.id == uuid.UUID(str(class_id)))

        classes = query.order_by(Kelas.grade, Kelas.name).all()
        return [_serialize(k, db) for k in classes]
    finally:
        db.close()


@router.post("")
def create_class(data: ClassIn, user: dict = Depends(require_role("admin"))):
    db = SessionLocal()
    try:
        exists = db.query(Kelas).filter(Kelas.name == data.name).first()
        if exists:
            raise HTTPException(400, "Nama kelas sudah ada")

        kelas = Kelas(
            id=uuid.uuid4(),
            name=data.name,
            grade=_parse_grade(data.grade),
            visible=True,
        )
        db.add(kelas)
        db.commit()
        db.refresh(kelas)
        return _serialize(kelas, db)
    finally:
        db.close()


@router.put("/{class_id}")
def update_class(class_id: uuid.UUID, data: ClassIn, user: dict = Depends(require_role("admin"))):
    db = SessionLocal()
    try:
        kelas = db.query(Kelas).filter(Kelas.id == class_id).first()
        if kelas is None:
            raise HTTPException(404, "Kelas tidak ditemukan")

        kelas.name = data.name
        kelas.grade = _parse_grade(data.grade)
        db.commit()
        db.refresh(kelas)
        return _serialize(kelas, db)
    finally:
        db.close()


@router.delete("/{class_id}")
def delete_class(class_id: uuid.UUID, user: dict = Depends(require_role("admin"))):
    db = SessionLocal()
    try:
        n = db.query(Siswa).filter(Siswa.class_id == class_id).count()
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
        grade = _parse_grade(data.grade)
        db.query(Kelas).filter(Kelas.grade == grade).update({"visible": data.visible})
        db.commit()
        return {
            "ok": True,
            "grade": grade,
            "grade_roman": GRADE_TO_ROMAN[grade],
            "visible": data.visible,
        }
    finally:
        db.close()
