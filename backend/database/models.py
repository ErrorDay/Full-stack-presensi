"""
models.py

Seluruh model database Attendance AI
"""

from datetime import datetime, date, time

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)

from database.base import Base


# ======================================================
# KELAS
# ======================================================

class Kelas(Base):
    __tablename__ = "kelas"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    nama: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False
    )

    tingkat: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )

    jurusan: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    tahun_ajaran: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    aktif: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    visible: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )
    # ^ ditambahkan untuk fitur "Sembunyikan" per tingkat di halaman
    # Kelas & Siswa (frontend React) -- beda dari `aktif` yang berarti
    # kelas masih dipakai tahun ajaran ini.

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    siswa = relationship(
        "Siswa",
        back_populates="kelas",
        cascade="all, delete-orphan"
    )

# ======================================================
# SISWA
# ======================================================

class Siswa(Base):
    __tablename__ = "siswa"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    nis: Mapped[str | None] = mapped_column(
        String(30),
        unique=True,
        nullable=True
    )

    nama: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    kelas_id: Mapped[int] = mapped_column(
        ForeignKey("kelas.id"),
        nullable=False
    )

    jenis_kelamin: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="AKTIF"
    )

    angkatan: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )
    # ^ Independen dari kelas_id -- angkatan (kohort masuk, mis. "4", "5", "6")
    # tetap sama selama 3 tahun walau siswa pindah/di-reshuffle antar kelas
    # tiap kenaikan tingkat. Dipakai untuk "Luluskan Angkatan" (nonaktifkan
    # semua siswa satu angkatan sekaligus, apapun kelasnya sekarang).

    foto: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    kelas = relationship(
        "Kelas",
        back_populates="siswa"
    )

    absensi = relationship(
        "Absensi",
        back_populates="siswa",
        cascade="all, delete-orphan"
    )

    embedding = relationship(
        "FaceEmbedding",
        back_populates="siswa",
        uselist=False,
        cascade="all, delete-orphan"
    )

    kunjungan = relationship(
        "Kunjungan",
        back_populates="siswa",
        cascade="all, delete-orphan"
    )


# ======================================================
# ABSENSI
# ======================================================

class Absensi(Base):
    __tablename__ = "absensi"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    siswa_id: Mapped[int] = mapped_column(
        ForeignKey("siswa.id"),
        nullable=False
    )

    tanggal: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    jam_masuk: Mapped[time] = mapped_column(
        Time,
        nullable=False
    )

    jam_keluar: Mapped[time | None] = mapped_column(
        Time,
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    keterangan: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    siswa = relationship(
        "Siswa",
        back_populates="absensi"
    )


# ======================================================
# USER
# ======================================================

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    nama: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    role: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    kelas_id: Mapped[int | None] = mapped_column(
        ForeignKey("kelas.id"),
        nullable=True
        # Hanya diisi kalau role="walas" -- menentukan kelas mana yang
        # boleh diakses/dikoreksi walas ini. NULL untuk admin/operator.
    )

    kelas = relationship("Kelas")

    aktif: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

# ======================================================
# FACE EMBEDDING
# ======================================================

class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    siswa_id: Mapped[int] = mapped_column(
        ForeignKey("siswa.id"),
        unique=True,
        nullable=False
    )

    embedding: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    siswa = relationship(
        "Siswa",
        back_populates="embedding"
    )

class HariLibur(Base):
    __tablename__ = "hari_libur"

    id = Column(Integer, primary_key=True)
    tanggal = Column(Date, unique=True, nullable=False)
    keterangan = Column(String, nullable=True)  # misal: "Idul Fitri"


# ======================================================
# SETTING
# Tabel singleton — idealnya cuma 1 baris (setting global sekolah)
# ======================================================

class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    jam_masuk: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        default=time(7, 0)  # default 07:00
    )

    toleransi_menit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10  # default toleransi 10 menit -> batas hadir 07:10
    )

    hari_sekolah: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[0,1,2,3,4]"
        # JSON list hari sekolah (0=Senin..6=Minggu), dipakai kalender.py
        # untuk is_hari_sekolah() -- dulu hardcode Sabtu/Minggu libur,
        # sekarang configurable sesuai kebutuhan frontend Pengaturan.jsx.
        # Hari libur TANGGAL SPESIFIK tetap pakai tabel HariLibur terpisah
        # (single source of truth), bukan disimpan di sini.
    )

    fr_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="local"
        # "local" karena recognition kita jalan langsung di proses
        # FastAPI yang sama (bukan panggil endpoint eksternal terpisah
        # seperti opsi "endpoint" di desain awal Emergent).
    )

    fr_endpoint_url: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


# ======================================================
# KUNJUNGAN PERPUSTAKAAN
# Beda dari Absensi: BOLEH lebih dari 1 baris per siswa per hari
# (setiap kali discan di mode perpustakaan = 1 kunjungan baru)
# ======================================================

class Kunjungan(Base):
    __tablename__ = "kunjungan_perpustakaan"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    siswa_id: Mapped[int] = mapped_column(
        ForeignKey("siswa.id"),
        nullable=False
    )

    tanggal: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    waktu: Mapped[time] = mapped_column(
        Time,
        nullable=False
    )

    siswa = relationship(
        "Siswa",
        back_populates="kunjungan"
    )

