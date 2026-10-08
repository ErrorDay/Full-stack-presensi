"""SQLAdmin model views for the Supabase-backed schema."""

from sqladmin import Admin, ModelView

from auth import AdminAuth
from database.models import (
    Absensi,
    FaceEmbedding,
    HariLibur,
    Kelas,
    Kunjungan,
    Setting,
    Siswa,
    User,
)


class KelasAdmin(ModelView, model=Kelas):
    name = "Kelas"
    name_plural = "Kelas"
    icon = "fa-solid fa-chalkboard"
    column_list = [Kelas.id, Kelas.name, Kelas.grade, Kelas.visible, Kelas.created_at]
    column_searchable_list = [Kelas.name]
    column_sortable_list = [Kelas.name, Kelas.grade]
    form_columns = [Kelas.name, Kelas.grade, Kelas.visible]


class SiswaAdmin(ModelView, model=Siswa):
    name = "Siswa"
    name_plural = "Siswa"
    icon = "fa-solid fa-user-graduate"
    column_list = [
        Siswa.id,
        Siswa.nisn,
        Siswa.name,
        Siswa.gender,
        Siswa.class_id,
        Siswa.status,
        Siswa.foto,
        Siswa.angkatan,
    ]
    column_searchable_list = [Siswa.nisn, Siswa.name]
    column_sortable_list = [Siswa.name, Siswa.nisn, Siswa.status]
    form_columns = [
        Siswa.nisn,
        Siswa.name,
        Siswa.gender,
        Siswa.class_id,
        Siswa.status,
        Siswa.foto,
        Siswa.angkatan,
    ]


class AbsensiAdmin(ModelView, model=Absensi):
    name = "Absensi"
    name_plural = "Riwayat Absensi"
    icon = "fa-solid fa-clipboard-check"
    column_list = [
        Absensi.id,
        Absensi.student_id,
        Absensi.attendance_date,
        Absensi.checked_at,
        Absensi.status,
        Absensi.source,
        Absensi.created_by,
    ]
    column_sortable_list = [Absensi.attendance_date, Absensi.checked_at, Absensi.status]
    column_searchable_list = [Absensi.status, Absensi.source]
    form_columns = [
        Absensi.student_id,
        Absensi.attendance_date,
        Absensi.checked_at,
        Absensi.status,
        Absensi.source,
        Absensi.notes,
        Absensi.created_by,
    ]


class FaceEmbeddingAdmin(ModelView, model=FaceEmbedding):
    name = "Face Embedding"
    name_plural = "Face Embeddings"
    icon = "fa-solid fa-id-badge"
    column_list = [
        FaceEmbedding.id,
        FaceEmbedding.student_id,
        FaceEmbedding.model,
        FaceEmbedding.created_at,
    ]
    can_create = False
    can_edit = False


class UserAdmin(ModelView, model=User):
    name = "User"
    name_plural = "User Admin"
    icon = "fa-solid fa-user-shield"
    column_list = [
        User.id,
        User.username,
        User.nama,
        User.role,
        User.kelas_id,
        User.created_at,
    ]
    column_searchable_list = [User.username, User.nama]
    # Account rows reference Supabase Auth IDs. Create accounts with create_user.py.
    can_create = False
    form_columns = [User.username, User.nama, User.role, User.kelas_id]


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
    column_list = [
        Setting.id,
        Setting.jam_masuk,
        Setting.batas_terlambat_menit,
        Setting.hari_sekolah,
        Setting.fr_mode,
        Setting.updated_at,
    ]
    form_columns = [
        Setting.jam_masuk,
        Setting.batas_terlambat_menit,
        Setting.hari_sekolah,
        Setting.fr_mode,
        Setting.fr_endpoint_url,
    ]
    can_create = False
    can_delete = False


class KunjunganAdmin(ModelView, model=Kunjungan):
    name = "Kunjungan Perpustakaan"
    name_plural = "Kunjungan Perpustakaan"
    icon = "fa-solid fa-book-open"
    column_list = [
        Kunjungan.id,
        Kunjungan.student_id,
        Kunjungan.visited_at,
        Kunjungan.source,
        Kunjungan.created_by,
    ]
    column_sortable_list = [Kunjungan.visited_at]
    can_create = False
    can_edit = False


def setup_admin(app, engine, secret_key: str):
    admin = Admin(
        app,
        engine,
        title="Presensi Face Recognition",
        authentication_backend=AdminAuth(secret_key=secret_key),
    )
    for model_view in (
        KelasAdmin,
        SiswaAdmin,
        AbsensiAdmin,
        FaceEmbeddingAdmin,
        UserAdmin,
        HariLiburAdmin,
        SettingAdmin,
        KunjunganAdmin,
    ):
        admin.add_view(model_view)
    return admin
