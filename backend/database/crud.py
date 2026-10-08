import uuid

from database.models import Kelas, Siswa
from database.session import SessionLocal

GRADE_BY_ROMAN = {"X": 10, "XI": 11, "XII": 12}


def _normalize_grade(grade: int | str | None, class_name: str) -> int:
    class_grade = class_name.split(maxsplit=1)
    value = grade if grade is not None else (class_grade[0] if class_grade else "")
    if isinstance(value, str):
        value = GRADE_BY_ROMAN.get(value.strip().upper(), value.strip())
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Grade kelas tidak valid: {value!r}") from exc
    if normalized not in (10, 11, 12):
        raise ValueError(f"Grade kelas harus 10, 11, atau 12: {normalized}")
    return normalized


def get_or_create_kelas(
    name: str,
    grade: int | str | None = None,
    visible: bool = True,
) -> Kelas:
    db = SessionLocal()
    try:
        kelas = db.query(Kelas).filter(Kelas.name == name).first()
        if kelas:
            return kelas

        kelas = Kelas(
            id=uuid.uuid4(),
            name=name,
            grade=_normalize_grade(grade, name),
            visible=visible,
        )
        db.add(kelas)
        db.commit()
        db.refresh(kelas)
        return kelas
    finally:
        db.close()


def get_or_create_siswa(
    name: str,
    class_id: uuid.UUID,
    nisn: str | None = None,
    gender: str | None = None,
    foto: str | None = None,
    angkatan: str | None = None,
) -> Siswa | None:
    db = SessionLocal()
    try:
        query = db.query(Siswa)
        if nisn:
            siswa = query.filter(Siswa.nisn == nisn).first()
        else:
            siswa = (
                query.filter(Siswa.name == name, Siswa.class_id == class_id)
                .first()
            )

        if siswa:
            siswa.foto = foto or siswa.foto
            if angkatan is not None:
                siswa.angkatan = angkatan
            db.commit()
            db.refresh(siswa)
            return siswa

        if not nisn or not gender:
            return None

        siswa = Siswa(
            id=uuid.uuid4(),
            nisn=nisn,
            name=name,
            gender=gender,
            class_id=class_id,
            foto=foto,
            angkatan=angkatan,
        )
        db.add(siswa)
        db.commit()
        db.refresh(siswa)
        return siswa
    finally:
        db.close()
