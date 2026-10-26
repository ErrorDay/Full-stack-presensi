"""
create_user.py
Script CLI untuk membuat akun admin/operator/walas.

Dijalankan manual dari terminal (bukan lewat form SQLAdmin), karena
password perlu di-hash (bcrypt) dulu sebelum disimpan — SQLAdmin form
biasa akan menyimpan teks polos kalau tidak ditangani khusus.

Setelah akun pertama dibuat, admin bisa membuat operator tambahan
langsung dari halaman admin (User) — TAPI perlu logic khusus supaya
password di-hash saat create/edit lewat form (akan dibahas saat
membangun halaman login di tahap 4).

Cara pakai:
    python create_user.py
"""

import getpass

from database.session import SessionLocal
from database.models import User
from auth import ROLES, hash_password


def create_user():
    db = SessionLocal()

    try:
        username = input("Username: ").strip()

        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"[GAGAL] Username '{username}' sudah dipakai.")
            return

        nama = input("Nama lengkap: ").strip()
        role = input("Role (admin/operator/walas): ").strip().lower() or "operator"
        if role not in ROLES:
            print(f"[GAGAL] Role harus salah satu dari: {', '.join(ROLES)}.")
            return
        password = getpass.getpass("Password: ")
        password_confirm = getpass.getpass("Ulangi password: ")

        if password != password_confirm:
            print("[GAGAL] Password tidak sama.")
            return

        if len(password) < 8:
            print("[GAGAL] Password minimal 8 karakter.")
            return

        user = User(
            username=username,
            password_hash=hash_password(password),
            nama=nama,
            role=role,
            aktif=True,
        )

        db.add(user)
        db.commit()

        print(f"[OK] Akun '{username}' ({role}) berhasil dibuat.")

    finally:
        db.close()


if __name__ == "__main__":
    create_user()
