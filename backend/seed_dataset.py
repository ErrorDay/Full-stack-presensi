"""Seed class folders and synchronize known student photo paths."""

import uuid
from pathlib import Path

from database.models import Kelas, Siswa
from database.session import SessionLocal

GRADE_BY_ROMAN = {"X": 10, "XI": 11, "XII": 12}
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def _grade_from_class_name(name: str) -> int:
    parts = name.split(maxsplit=1)
    token = parts[0].upper() if parts else ""
    if token in GRADE_BY_ROMAN:
        return GRADE_BY_ROMAN[token]
    try:
        grade = int(token)
    except ValueError as exc:
        raise ValueError(f"Nama folder kelas harus diawali X/XI/XII atau 10/11/12: {name}") from exc
    if grade not in (10, 11, 12):
        raise ValueError(f"Grade kelas harus 10, 11, atau 12: {name}")
    return grade


def get_or_create_kelas(db, name: str) -> Kelas:
    kelas = db.query(Kelas).filter(Kelas.name == name).first()
    if kelas:
        return kelas

    kelas = Kelas(
        id=uuid.uuid4(),
        name=name,
        grade=_grade_from_class_name(name),
        visible=True,
    )
    db.add(kelas)
    db.commit()
    db.refresh(kelas)
    print(f"[KELAS] {name} ({kelas.grade})")
    return kelas


def get_or_create_siswa(
    db,
    name: str,
    class_id: uuid.UUID,
    foto: str,
) -> Siswa | None:
    siswa = (
        db.query(Siswa)
        .filter(Siswa.name == name, Siswa.class_id == class_id)
        .first()
    )
    if siswa:
        siswa.foto = foto
        db.commit()
        return siswa

    print(
        f"[SKIP] {name}: tidak dibuat karena dataset tidak menyediakan "
        "nisn dan gender yang diwajibkan skema Supabase."
    )
    return None


def seed_dataset() -> None:
    dataset_folder = Path("dataset")
    if not dataset_folder.is_dir():
        print("Folder dataset tidak ditemukan.")
        return

    db = SessionLocal()
    total_kelas = 0
    total_siswa_dikenali = 0
    total_siswa_baru_dilewati = 0

    try:
        for folder_kelas in dataset_folder.iterdir():
            if not folder_kelas.is_dir():
                continue

            nama_kelas = folder_kelas.name.replace("_", " ").strip().upper()
            try:
                kelas = get_or_create_kelas(db, nama_kelas)
            except ValueError as exc:
                print(f"[SKIP KELAS] {exc}")
                continue
            total_kelas += 1

            for foto in folder_kelas.iterdir():
                if foto.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
                    continue

                nama_siswa = foto.stem.replace("_", " ").strip().upper()
                siswa = get_or_create_siswa(
                    db, nama_siswa, kelas.id, str(foto)
                )
                if siswa is None:
                    total_siswa_baru_dilewati += 1
                else:
                    total_siswa_dikenali += 1

        print("\n========================")
        print("SEED DATASET SELESAI")
        print("========================")
        print(f"Kelas diproses            : {total_kelas}")
        print(f"Siswa existing diperbarui : {total_siswa_dikenali}")
        print(f"Siswa baru dilewati       : {total_siswa_baru_dilewati}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_dataset()
