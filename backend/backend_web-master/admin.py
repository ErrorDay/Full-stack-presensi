"""
admin.py
Setup SQLAdmin — pengganti Filament di versi Laravel / PySide6 form
manual di versi desktop lama.

Disusun berdasarkan database/models.py asli (dikonfirmasi):
Kelas, Siswa, Absensi, User, FaceEmbedding, HariLibur, Setting.
Database: PostgreSQL.
"""

from sqladmin import Admin, ModelView

from database.models import Kelas, Siswa, Absensi, User, FaceEmbedding, HariLibur, Setting, Kunjungan
from auth import AdminAuth


class KelasAdmin(ModelView, model=Kelas):
    name = "Kelas"
    name_plural = "Kelas"
    icon = "fa-solid fa-chalkboard"

    column_list = [
        Kelas.id, Kelas.nama, Kelas.tingkat, Kelas.jurusan,
        Kelas.tahun_ajaran, Kelas.aktif, Kelas.visible,
    ]
    column_searchable_list = [Kelas.nama]
    column_sortable_list = [Kelas.nama, Kelas.tingkat, Kelas.tahun_ajaran]
    form_columns = [Kelas.nama, Kelas.tingkat, Kelas.jurusan, Kelas.tahun_ajaran, Kelas.aktif, Kelas.visible]


class SiswaAdmin(ModelView, model=Siswa):
    name = "Siswa"
    name_plural = "Siswa"
    icon = "fa-solid fa-user-graduate"

    column_list = [
        Siswa.id, Siswa.nis, Siswa.nama, Siswa.kelas_id,
        Siswa.jenis_kelamin, Siswa.status, Siswa.foto,
    ]
    column_searchable_list = [Siswa.nama, Siswa.nis]
    column_sortable_list = [Siswa.nama, Siswa.nis, Siswa.status]
    form_columns = [
        Siswa.nis, Siswa.nama, Siswa.kelas_id,
        Siswa.jenis_kelamin, Siswa.status, Siswa.foto,
    ]


class AbsensiAdmin(ModelView, model=Absensi):
    name = "Absensi"
    name_plural = "Riwayat Absensi"
    icon = "fa-solid fa-clipboard-check"

    column_list = [
        Absensi.id, Absensi.siswa_id, Absensi.tanggal,
        Absensi.jam_masuk, Absensi.jam_keluar,
        Absensi.status, Absensi.keterangan,
    ]
    column_sortable_list = [Absensi.tanggal, Absensi.status]
    column_searchable_list = [Absensi.status]
    # Absensi normalnya dibuat otomatis lewat proses recognize/scan,
    # tapi tetap dibuka untuk koreksi manual oleh admin.
    can_create = True
    can_edit = True


class FaceEmbeddingAdmin(ModelView, model=FaceEmbedding):
    name = "Face Embedding"
    name_plural = "Face Embeddings"
    icon = "fa-solid fa-id-badge"

    # siswa_id UNIQUE -> saat ini cuma 1 embedding per siswa.
    # Kolom "embedding" (Text/JSON panjang) sengaja tidak ditampilkan
    # di list, cukup terlihat di halaman detail.
    column_list = [FaceEmbedding.id, FaceEmbedding.siswa_id, FaceEmbedding.created_at]
    can_create = False  # enrollment lewat endpoint /api/siswa/{id}/enroll (tahap 3)
    can_edit = False


class UserAdmin(ModelView, model=User):
    name = "User"
    name_plural = "User Admin"
    icon = "fa-solid fa-user-shield"

    column_list = [User.id, User.username, User.nama, User.role, User.aktif]
    column_searchable_list = [User.username, User.nama]
    # password_hash sengaja TIDAK dimasukkan -- butuh handling hashing
    # khusus (lihat create_user.py), form_columns yang mendefinisikan
    # daftar field sudah cukup, tidak perlu form_excluded_columns juga
    # (SQLAdmin melarang pakai keduanya sekaligus).
    form_columns = [User.username, User.nama, User.role, User.aktif]


class HariLiburAdmin(ModelView, model=HariLibur):
    name = "Hari Libur"
    name_plural = "Hari Libur"
    icon = "fa-solid fa-calendar-xmark"

    column_list = [HariLibur.id, HariLibur.tanggal, HariLibur.keterangan]
    column_sortable_list = [HariLibur.tanggal]
    form_columns = [HariLibur.tanggal, HariLibur.keterangan]


class SettingAdmin(ModelView, model=Setting):
    name = "Pengaturan"
    name_plural = "Pengaturan"
    icon = "fa-solid fa-gear"

    # Tabel ini bersifat singleton — idealnya cuma 1 baris (setting global).
    column_list = [
        Setting.id, Setting.jam_masuk, Setting.toleransi_menit,
        Setting.hari_sekolah, Setting.fr_mode, Setting.updated_at,
    ]
    form_columns = [
        Setting.jam_masuk, Setting.toleransi_menit,
        Setting.hari_sekolah, Setting.fr_mode, Setting.fr_endpoint_url,
    ]


class KunjunganAdmin(ModelView, model=Kunjungan):
    name = "Kunjungan Perpustakaan"
    name_plural = "Kunjungan Perpustakaan"
    icon = "fa-solid fa-book-open"

    column_list = [Kunjungan.id, Kunjungan.siswa_id, Kunjungan.tanggal, Kunjungan.waktu]
    column_sortable_list = [Kunjungan.tanggal, Kunjungan.waktu]
    can_create = False  # dicatat otomatis lewat scan kamera, bukan input manual
    can_edit = False


def setup_admin(app, engine, secret_key: str):
    """
    Daftarkan seluruh ModelView ke instance FastAPI, plus AdminAuth
    supaya /admin butuh login (lihat auth.py).
    Dipanggil dari main.py.

    Halaman kamera live "Presensi" (seperti screenshot referensi)
    akan ditambahkan di sini sebagai custom BaseView pada tahap 4,
    sekaligus halaman login untuk akun operator.
    """

    admin = Admin(
        app,
        engine,
        title="Presensi Face Recognition",
        authentication_backend=AdminAuth(secret_key=secret_key),
    )

    admin.add_view(KelasAdmin)
    admin.add_view(SiswaAdmin)
    admin.add_view(AbsensiAdmin)
    admin.add_view(FaceEmbeddingAdmin)
    admin.add_view(UserAdmin)
    admin.add_view(HariLiburAdmin)
    admin.add_view(SettingAdmin)
    admin.add_view(KunjunganAdmin)

    return admin
