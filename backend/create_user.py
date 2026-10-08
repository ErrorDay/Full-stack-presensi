"""Set up a local password/role for an existing Supabase Auth user."""

import getpass
import uuid

from auth import ROLES, hash_password
from database.models import Kelas, User
from database.session import SessionLocal


def create_user() -> None:
    print(
        "Masukkan UUID akun yang SUDAH ADA di Supabase Auth "
        "(users.id mereferensikan auth.users.id)."
    )
    try:
        user_id = uuid.UUID(input("Supabase Auth user UUID: ").strip())
    except ValueError:
        print("[GAGAL] UUID Supabase Auth tidak valid.")
        return

    username = input("Username: ").strip()
    nama = input("Nama lengkap: ").strip()
    role = input("Role (admin/operator/walas): ").strip().lower() or "operator"
    if role not in ROLES:
        print(f"[GAGAL] Role harus salah satu dari: {', '.join(ROLES)}.")
        return

    kelas_id = None
    if role == "walas":
        try:
            kelas_id = uuid.UUID(input("UUID kelas untuk walas: ").strip())
        except ValueError:
            print("[GAGAL] UUID kelas tidak valid.")
            return

    password = getpass.getpass("Password lokal: ")
    password_confirm = getpass.getpass("Ulangi password: ")
    if password != password_confirm:
        print("[GAGAL] Password tidak sama.")
        return
    if len(password) < 8:
        print("[GAGAL] Password minimal 8 karakter.")
        return
    if not username or not nama:
        print("[GAGAL] Username dan nama wajib diisi.")
        return

    db = SessionLocal()
    try:
        existing_id = db.query(User).filter(User.id == user_id).first()
        existing_username = (
            db.query(User).filter(User.username == username).first()
        )
        if existing_username and existing_username.id != user_id:
            print(f"[GAGAL] Username '{username}' sudah dipakai.")
            return
        if existing_id:
            existing_id.username = username
            existing_id.password_hash = hash_password(password)
            existing_id.nama = nama
            existing_id.role = role
            existing_id.kelas_id = kelas_id
            db.commit()
            print(f"[OK] Profil lokal '{username}' ({role}) berhasil disimpan.")
            return

        if kelas_id is not None and db.query(Kelas.id).filter(Kelas.id == kelas_id).first() is None:
            print("[GAGAL] Kelas UUID tidak ditemukan.")
            return

        user = User(
            id=user_id,
            username=username,
            password_hash=hash_password(password),
            nama=nama,
            role=role,
            kelas_id=kelas_id,
        )
        db.add(user)
        db.commit()
        print(f"[OK] Profil lokal '{username}' ({role}) berhasil dibuat.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_user()
