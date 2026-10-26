"""
sync_dataset_foto.py

Maintenance script -- dipakai SEKALI setiap kali folder dataset/
direorganisasi (nama file/format foto berubah) sehingga path lama
di kolom Siswa.foto sudah tidak valid lagi.

v2 -- perbaikan dari versi pertama setelah ketahuan 2 masalah:

1. Siswa.nama di database ternyata masih menyimpan angka "(N)" yang
   dulu ke-parse dari nama file foto lama (mis. "ABDUL FAKHRY
   WICAKSONO (4)"), padahal file foto baru TIDAK punya angka itu.
   -> Sekarang di-strip dulu dengan regex sebelum dicocokkan.

2. Siswa yang sudah pernah dipindah kelas (migrasi) foto fisiknya
   TETAP di folder kelas LAMA (migrasi cuma update database, tidak
   memindahkan file). -> Sekarang search fallback ke SEMUA subfolder
   dataset/, bukan cuma folder kelas yang tercatat di database saat ini.

3. Record dengan nama seperti "DSC_0531" (nama file kamera otomatis,
   bukan nama orang) dilaporkan terpisah sebagai kemungkinan data
   sampah, bukan dianggap "siswa yang fotonya hilang".

Cara pakai:
    python sync_dataset_foto.py
"""

import os
import re

from database.session import SessionLocal
from database.models import Siswa, Kelas

DATASET_DIR = "dataset"
EKSTENSI_DICOBA = [".png", ".PNG", ".jpg", ".JPG", ".jpeg", ".JPEG"]

# Pola nama file kamera otomatis (DSC_1234, IMG_1234, dst) -- indikasi
# kuat ini BUKAN nama siswa asli, kemungkinan salah ke-import saat
# seeding pertama kali.
POLA_NAMA_FILE_KAMERA = re.compile(r"^(DSC|IMG|PXL|WA)[\s_]?\d+$", re.IGNORECASE)


def bersihkan_nama(nama: str) -> str:
    """
    Buang angka " (N)" di akhir nama yang ke-parse keliru dari nama
    file foto lama. "ABDUL FAKHRY WICAKSONO (4)" -> "ABDUL FAKHRY WICAKSONO"
    """
    return re.sub(r"\s*\(\d+\)\s*$", "", nama).strip()


def build_index_semua_foto() -> dict:
    """
    Scan SEMUA file di dalam dataset/ (semua subfolder kelas, apapun
    namanya), bikin index: nama_file_tanpa_ekstensi (UPPER) -> path lengkap.
    Dipakai untuk fallback pencarian lintas folder (kasus siswa yang
    sudah migrasi kelas, fotonya masih di folder kelas lama).
    """
    index = {}
    if not os.path.isdir(DATASET_DIR):
        return index

    for root, _dirs, files in os.walk(DATASET_DIR):
        for f in files:
            stem, ext = os.path.splitext(f)
            if ext.lower() not in [e.lower() for e in EKSTENSI_DICOBA]:
                continue
            index[stem.strip().upper()] = os.path.join(root, f)

    return index


def sync_dataset_foto():
    db = SessionLocal()

    diperbarui = 0
    tidak_ketemu = []
    kemungkinan_sampah = []
    sudah_benar = 0

    try:
        index_foto = build_index_semua_foto()
        print(f"[INFO] {len(index_foto)} file foto terindeks dari seluruh folder dataset/\n")

        siswa_list = (
            db.query(Siswa, Kelas)
            .join(Kelas, Siswa.kelas_id == Kelas.id)
            .all()
        )

        for siswa, kelas in siswa_list:

            nama_bersih = bersihkan_nama(siswa.nama)

            if POLA_NAMA_FILE_KAMERA.match(nama_bersih):
                kemungkinan_sampah.append(f"{siswa.nama} (id={siswa.id}, {kelas.nama})")
                continue

            # 1) coba dulu di folder kelas SAAT INI
            path_baru = None
            for ext in EKSTENSI_DICOBA:
                kandidat = os.path.join(DATASET_DIR, kelas.nama, f"{nama_bersih}{ext}")
                if os.path.exists(kandidat):
                    path_baru = kandidat
                    break

            # 2) kalau tidak ketemu, fallback cari di SELURUH dataset/
            #    (kasus siswa sudah migrasi kelas, foto masih di folder lama)
            if path_baru is None:
                path_baru = index_foto.get(nama_bersih.upper())

            if path_baru is None:
                tidak_ketemu.append(f"{siswa.nama} (id={siswa.id}, {kelas.nama})")
                continue

            if siswa.foto == path_baru:
                sudah_benar += 1
                continue

            print(f"[UPDATE] {siswa.nama}: {siswa.foto!r} -> {path_baru!r}")
            siswa.foto = path_baru
            diperbarui += 1

        db.commit()

        print("\n====================")
        print("SYNC SELESAI")
        print("====================")
        print(f"Diperbarui         : {diperbarui}")
        print(f"Sudah benar        : {sudah_benar}")
        print(f"Tidak ketemu       : {len(tidak_ketemu)}")
        print(f"Kemungkinan sampah : {len(kemungkinan_sampah)}")

        if kemungkinan_sampah:
            print("\n--- KEMUNGKINAN DATA SAMPAH (nama file kamera, bukan nama siswa) ---")
            for s in kemungkinan_sampah:
                print(f"  {s}")

        if tidak_ketemu:
            print("\n--- BENAR-BENAR TIDAK KETEMU (perlu dicek manual) ---")
            for s in tidak_ketemu:
                print(f"  {s}")

        print("\nLangkah selanjutnya: jalankan `python generate_embeddings.py`")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")

    finally:
        db.close()


if __name__ == "__main__":
    sync_dataset_foto()
