from pathlib import Path
from sqlalchemy import func

from database.session import SessionLocal
from database.models import Kelas, Siswa


def get_or_create_kelas(db, nama_kelas):
    kelas = (
        db.query(Kelas)
        .filter(
            func.upper(
                func.trim(Kelas.nama)
            ) == nama_kelas
        )
        .first()
    )

    if kelas:
        return kelas

    parts = nama_kelas.split()

    tingkat = parts[0] if parts else ""
    jurusan = " ".join(parts[1:]) if len(parts) > 1 else ""

    kelas = Kelas(
        nama=nama_kelas,
        tingkat=tingkat,
        jurusan=jurusan,
        tahun_ajaran="2026/2027",
        aktif=True
    )

    db.add(kelas)
    db.commit()
    db.refresh(kelas)

    print(f"[KELAS] {nama_kelas}")

    return kelas


def get_or_create_siswa(
        db,
        nama_siswa,
        kelas_id,
        foto
):
    siswa = (
        db.query(Siswa)
        .filter(Siswa.nama == nama_siswa)
        .first()
    )

    if siswa:
        return siswa

    siswa = Siswa(
        nama=nama_siswa,
        nis=None,
        kelas_id=kelas_id,
        jenis_kelamin=None,
        status="AKTIF",
        foto=foto
    )

    db.add(siswa)
    db.commit()
    db.refresh(siswa)

    print(f"[SISWA] {nama_siswa}")

    return siswa


def seed_dataset():
    dataset_folder = Path("dataset")

    if not dataset_folder.exists():
        print("Folder dataset tidak ditemukan.")
        return

    db = SessionLocal()

    try:
        total_kelas = 0
        total_siswa = 0

        for folder_kelas in dataset_folder.iterdir():

            if not folder_kelas.is_dir():
                continue

            nama_kelas = (
                folder_kelas.name
                .replace("_", " ")
                .strip()
                .upper()
            )

            kelas = get_or_create_kelas(
                db,
                nama_kelas
            )

            total_kelas += 1

            for foto in folder_kelas.iterdir():

                if foto.suffix.lower() not in [
                    ".jpg",
                    ".jpeg",
                    ".png"
                ]:
                    continue

                nama_siswa = (
                    foto.stem
                    .replace("_", " ")
                    .strip()
                    .upper()
                )

                siswa = get_or_create_siswa(
                    db,
                    nama_siswa,
                    kelas.id,
                    str(foto)
                )

                if siswa:
                    total_siswa += 1

        print("\n========================")
        print("SEED DATASET SELESAI")
        print("========================")
        print(f"Kelas : {total_kelas}")
        print(f"Siswa : {total_siswa}")

    except Exception as e:
        db.rollback()
        print("Terjadi kesalahan:")
        print(e)

    finally:
        db.close()


if __name__ == "__main__":
    seed_dataset()
