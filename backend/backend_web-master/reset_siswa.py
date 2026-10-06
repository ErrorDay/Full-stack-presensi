"""
reset_siswa.py

Hapus SEMUA data Siswa dari database -- dipakai untuk reset total
sebelum seeding ulang dari folder dataset/ yang sudah bersih (nama
file tanpa nomor "(N)"), supaya Siswa.nama juga otomatis bersih
sejak awal tanpa perlu strip manual.

Ikut terhapus otomatis (cascade lewat relationship di models.py):
  - FaceEmbedding (embedding wajah)
  - Absensi (riwayat presensi)
  - Kunjungan (riwayat kunjungan perpustakaan)

TIDAK ikut terhapus (sengaja dipertahankan):
  - Kelas (seed_dataset.py akan reuse kelas yang sudah ada, bukan
    bikin duplikat, karena get_or_create_kelas cek dulu by nama)
  - User, Setting, HariLibur

PERINGATAN: ini menghapus SEMUA riwayat absensi & kunjungan
perpustakaan yang sudah tercatat. Kalau ada data yang masih ingin
disimpan, backup dulu (export CSV dari halaman Presensi) sebelum run.

Cara pakai:
    python reset_siswa.py
"""

from database.session import SessionLocal
from database.models import Siswa


def reset_siswa():
    db = SessionLocal()

    try:
        total = db.query(Siswa).count()

        if total == 0:
            print("Tidak ada data Siswa, tidak perlu reset.")
            return

        print(f"Akan menghapus SEMUA {total} baris Siswa, beserta:")
        print("  - Semua FaceEmbedding (embedding wajah)")
        print("  - Semua Absensi (riwayat presensi)")
        print("  - Semua Kunjungan (riwayat kunjungan perpustakaan)")
        print("\nKelas, User, Setting, HariLibur TIDAK ikut terhapus.")

        konfirmasi = input("\nKetik 'RESET' (huruf besar semua) untuk melanjutkan: ")

        if konfirmasi.strip() != "RESET":
            print("Dibatalkan.")
            return

        siswa_list = db.query(Siswa).all()
        for s in siswa_list:
            db.delete(s)

        db.commit()

        print(f"\n[OK] {total} siswa (+ embedding, absensi, kunjungan terkait) berhasil dihapus.")
        print("\nLangkah selanjutnya:")
        print("  1. Pastikan folder dataset/ sudah bersih (hapus file DSC_xxxx yang bukan siswa)")
        print("  2. python seed_dataset.py")
        print("  3. python generate_embeddings.py")
        print("  4. Restart python main.py")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")

    finally:
        db.close()


if __name__ == "__main__":
    reset_siswa()
