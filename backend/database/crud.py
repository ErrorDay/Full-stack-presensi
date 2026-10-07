from database.session import SessionLocal
from database.models import Kelas


def get_or_create_kelas(nama: str, tahun_ajaran: str = "2026/2027"):
    """
    Diperbaiki: sebelumnya cuma mengisi nama + tingkat, padahal
    jurusan dan tahun_ajaran nullable=False di model Kelas -> akan
    gagal INSERT (NotNullViolation). Sekarang konsisten dengan
    parsing di seed_dataset.py.
    """
    db = SessionLocal()

    try:
        kelas = (
            db.query(Kelas)
            .filter(Kelas.nama == nama)
            .first()
        )

        if kelas:
            return kelas

        parts = nama.split()
        tingkat = parts[0] if parts else ""
        jurusan = " ".join(parts[1:]) if len(parts) > 1 else ""

        kelas = Kelas(
            nama=nama,
            tingkat=tingkat,
            jurusan=jurusan,
            tahun_ajaran=tahun_ajaran,
            aktif=True
        )

        db.add(kelas)
        db.commit()
        db.refresh(kelas)

        return kelas

    finally:
        db.close()

from database.models import Siswa


def get_or_create_siswa(
    nama: str,
    kelas_id: int,
    foto: str | None = None
):
    db = SessionLocal()

    try:
        siswa = (
            db.query(Siswa)
            .filter(Siswa.nama == nama)
            .first()
        )

        if siswa:
            return siswa

        siswa = Siswa(
            nama=nama,
            kelas_id=kelas_id,
            foto=foto
        )

        db.add(siswa)
        db.commit()
        db.refresh(siswa)

        return siswa

    finally:
        db.close()
