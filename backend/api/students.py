"""CRUD endpoints for student records."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from auth import require_role
from database.models import Kelas, Siswa
from database.session import SessionLocal

router = APIRouter()

STATUS_TO_DB = {"aktif": "Aktif", "nonaktif": "Nonaktif"}


def _normalize_status(status: str) -> str:
    normalized = STATUS_TO_DB.get(status.strip().casefold())
    if normalized is None:
        raise HTTPException(400, "Status harus Aktif atau Nonaktif")
    return normalized


def _serialize(siswa: Siswa, kelas: Kelas | None = None) -> dict:
    kelas = kelas if kelas is not None else siswa.kelas
    return {
        "id": str(siswa.id),
        "nisn": siswa.nisn,
        "name": siswa.name,
        "gender": siswa.gender,
        "class_id": str(siswa.class_id) if siswa.class_id else None,
        "class_name": kelas.name if kelas else "",
        "grade": kelas.grade if kelas else None,
        "status": siswa.status,
        "foto": siswa.foto,
        "angkatan": siswa.angkatan,
    }


class StudentIn(BaseModel):
    nisn: str
    name: str
    gender: Literal["L", "P"]
    class_id: uuid.UUID | None = None
    status: str = "Aktif"
    foto: str | None = None
    angkatan: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = STATUS_TO_DB.get(value.strip().casefold())
        if normalized is None:
            raise ValueError("Status harus Aktif atau Nonaktif")
        return normalized


class MigrateIn(BaseModel):
    class_id: uuid.UUID


class AssignBulkIn(BaseModel):
    class_id: uuid.UUID
    student_ids: list[uuid.UUID]


class BulkStatusIn(BaseModel):
    class_id: uuid.UUID
    status: str


class BulkStatusAngkatanIn(BaseModel):
    angkatan: str
    status: str


class SetAngkatanIn(BaseModel):
    class_id: uuid.UUID
    angkatan: str


@router.get("")
def list_students(
    class_id: uuid.UUID | None = None,
    angkatan: str | None = None,
    q: str | None = None,
    status: str | None = "Aktif",
    user: dict = Depends(require_role("admin", "operator", "walas")),
):
    db = SessionLocal()
    try:
        query = db.query(Siswa)
        if user["role"] == "walas":
            assigned_class = user.get("kelas_id")
            if not assigned_class:
                return []
            try:
                class_id = uuid.UUID(str(assigned_class))
            except ValueError as exc:
                raise HTTPException(403, "Kelas akun walas tidak valid") from exc
        if class_id:
            query = query.filter(Siswa.class_id == class_id)

        if angkatan:
            query = query.filter(Siswa.angkatan == angkatan)

        if status and status.lower() != "semua":
            query = query.filter(Siswa.status == _normalize_status(status))

        if q:
            query = query.filter(Siswa.name.ilike(f"%{q}%"))

        siswa_list = query.order_by(Siswa.name).all()
        return [_serialize(siswa) for siswa in siswa_list]
    finally:
        db.close()


@router.post("")
def create_student(data: StudentIn, user: dict = Depends(require_role("admin"))):
    db = SessionLocal()
    try:
        kelas = None
        if data.class_id is not None:
            kelas = db.query(Kelas).filter(Kelas.id == data.class_id).first()
            if kelas is None:
                raise HTTPException(404, "Kelas tidak ditemukan")

        if db.query(Siswa).filter(Siswa.nisn == data.nisn).first():
            raise HTTPException(400, "NISN sudah terdaftar")

        siswa = Siswa(
            id=uuid.uuid4(),
            nisn=data.nisn,
            name=data.name,
            gender=data.gender,
            class_id=data.class_id,
            status=data.status,
            foto=data.foto,
            angkatan=data.angkatan,
        )
        db.add(siswa)
        db.commit()
        db.refresh(siswa)
        return _serialize(siswa, kelas)
    finally:
        db.close()


@router.post("/assign-bulk")
def assign_students_bulk(
    data: AssignBulkIn, user: dict = Depends(require_role("admin"))
):
    db = SessionLocal()
    try:
        kelas = db.query(Kelas).filter(Kelas.id == data.class_id).first()
        if kelas is None:
            raise HTTPException(404, "Kelas tidak ditemukan")

        moved = (
            db.query(Siswa)
            .filter(Siswa.id.in_(data.student_ids))
            .update({"class_id": kelas.id}, synchronize_session=False)
        )
        db.commit()
        return {"ok": True, "moved": moved, "class_id": str(kelas.id)}
    finally:
        db.close()


@router.post("/set-angkatan")
def set_angkatan(data: SetAngkatanIn, user: dict = Depends(require_role("admin"))):
    db = SessionLocal()
    try:
        kelas = db.query(Kelas).filter(Kelas.id == data.class_id).first()
        if kelas is None:
            raise HTTPException(404, "Kelas tidak ditemukan")

        jumlah = (
            db.query(Siswa)
            .filter(Siswa.class_id == kelas.id)
            .update({"angkatan": data.angkatan}, synchronize_session=False)
        )
        db.commit()
        return {
            "ok": True,
            "jumlah": jumlah,
            "class_id": str(kelas.id),
            "angkatan": data.angkatan,
        }
    finally:
        db.close()


@router.post("/bulk-status")
def bulk_status(
    data: BulkStatusIn,
    request: Request,
    user: dict = Depends(require_role("admin")),
):
    db = SessionLocal()
    try:
        kelas = db.query(Kelas).filter(Kelas.id == data.class_id).first()
        if kelas is None:
            raise HTTPException(404, "Kelas tidak ditemukan")

        status = _normalize_status(data.status)
        jumlah = (
            db.query(Siswa)
            .filter(Siswa.class_id == kelas.id)
            .update({"status": status}, synchronize_session=False)
        )
        db.commit()
        request.app.state.recognition.reload_embeddings()
        return {
            "ok": True,
            "jumlah": jumlah,
            "class_id": str(kelas.id),
            "status": status,
        }
    finally:
        db.close()


@router.post("/bulk-status-angkatan")
def bulk_status_angkatan(
    data: BulkStatusAngkatanIn,
    request: Request,
    user: dict = Depends(require_role("admin")),
):
    db = SessionLocal()
    try:
        status = _normalize_status(data.status)
        jumlah = (
            db.query(Siswa)
            .filter(Siswa.angkatan == data.angkatan)
            .update({"status": status}, synchronize_session=False)
        )
        db.commit()
        request.app.state.recognition.reload_embeddings()
        return {
            "ok": True,
            "jumlah": jumlah,
            "angkatan": data.angkatan,
            "status": status,
        }
    finally:
        db.close()


@router.put("/{student_id}")
def update_student(
    student_id: uuid.UUID,
    data: StudentIn,
    request: Request,
    user: dict = Depends(require_role("admin")),
):
    db = SessionLocal()
    try:
        siswa = db.query(Siswa).filter(Siswa.id == student_id).first()
        if siswa is None:
            raise HTTPException(404, "Siswa tidak ditemukan")

        kelas = None
        if data.class_id is not None:
            kelas = db.query(Kelas).filter(Kelas.id == data.class_id).first()
            if kelas is None:
                raise HTTPException(404, "Kelas tidak ditemukan")

        duplicate = (
            db.query(Siswa)
            .filter(Siswa.nisn == data.nisn, Siswa.id != student_id)
            .first()
        )
        if duplicate:
            raise HTTPException(400, "NISN sudah terdaftar")

        status_changed = siswa.status != data.status
        siswa.nisn = data.nisn
        siswa.name = data.name
        siswa.gender = data.gender
        siswa.class_id = data.class_id
        siswa.status = data.status
        siswa.foto = data.foto
        siswa.angkatan = data.angkatan
        db.commit()
        db.refresh(siswa)

        if status_changed:
            request.app.state.recognition.reload_embeddings()

        return _serialize(siswa, kelas)
    finally:
        db.close()


@router.delete("/{student_id}")
def delete_student(
    student_id: uuid.UUID, user: dict = Depends(require_role("admin"))
):
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
def migrate_student(
    student_id: uuid.UUID,
    data: MigrateIn,
    user: dict = Depends(require_role("admin")),
):
    db = SessionLocal()
    try:
        kelas = db.query(Kelas).filter(Kelas.id == data.class_id).first()
        if kelas is None:
            raise HTTPException(404, "Kelas tujuan tidak ditemukan")

        siswa = db.query(Siswa).filter(Siswa.id == student_id).first()
        if siswa is None:
            raise HTTPException(404, "Siswa tidak ditemukan")

        siswa.class_id = kelas.id
        db.commit()
        db.refresh(siswa)
        return _serialize(siswa, kelas)
    finally:
        db.close()
