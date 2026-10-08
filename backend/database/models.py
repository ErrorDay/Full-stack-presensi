"""SQLAlchemy models for the attendance application."""

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from database.base import Base


class Kelas(Base):
    __tablename__ = "kelas"
    __table_args__ = (
        CheckConstraint("grade BETWEEN 10 AND 12", name="kelas_grade_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    grade: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    siswa: Mapped[list["Siswa"]] = relationship(
        back_populates="kelas", passive_deletes=True
    )


class Siswa(Base):
    __tablename__ = "siswa"
    __table_args__ = (
        CheckConstraint("gender IN ('L', 'P')", name="siswa_gender_check"),
        CheckConstraint(
            "status IN ('Aktif', 'Nonaktif')", name="siswa_status_check"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    nisn: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    gender: Mapped[str] = mapped_column(Text, nullable=False)
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kelas.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="Aktif",
        server_default=text("'Aktif'"),
    )
    foto: Mapped[str | None] = mapped_column(Text, nullable=True)
    angkatan: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    kelas: Mapped["Kelas | None"] = relationship(back_populates="siswa")
    absensi: Mapped[list["Absensi"]] = relationship(
        back_populates="siswa", passive_deletes=True
    )
    embeddings: Mapped[list["FaceEmbedding"]] = relationship(
        back_populates="siswa", passive_deletes=True
    )
    kunjungan: Mapped[list["Kunjungan"]] = relationship(
        back_populates="siswa", passive_deletes=True
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'operator', 'walas')", name="users_role_check"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    nama: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="operator",
        server_default=text("'operator'"),
    )
    kelas_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kelas.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    kelas: Mapped["Kelas | None"] = relationship()


class Absensi(Base):
    __tablename__ = "absensi"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "attendance_date", name="absensi_student_date_key"
        ),
        CheckConstraint(
            "status IN ('Tidak Terlambat', 'Terlambat', 'Izin', 'Alpa')",
            name="absensi_status_check",
        ),
        CheckConstraint(
            "source IN ('face', 'manual', 'import')",
            name="absensi_source_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("siswa.id", ondelete="CASCADE"),
        nullable=False,
    )
    attendance_date: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(
        Text, nullable=False, default="face", server_default=text("'face'")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    siswa: Mapped["Siswa"] = relationship(back_populates="absensi")
    creator: Mapped["User | None"] = relationship()


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("siswa.id", ondelete="CASCADE"),
        nullable=False,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(512), nullable=False)
    model: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="buffalo_l",
        server_default=text("'buffalo_l'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    siswa: Mapped["Siswa"] = relationship(back_populates="embeddings")


class Kunjungan(Base):
    __tablename__ = "kunjungan_perpustakaan"
    __table_args__ = (
        CheckConstraint(
            "source IN ('face', 'manual')", name="kunjungan_source_check"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("siswa.id", ondelete="CASCADE"),
        nullable=False,
    )
    visited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    source: Mapped[str] = mapped_column(
        Text, nullable=False, default="face", server_default=text("'face'")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    siswa: Mapped["Siswa"] = relationship(back_populates="kunjungan")
    creator: Mapped["User | None"] = relationship()


class HariLibur(Base):
    __tablename__ = "hari_libur"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tanggal: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    keterangan: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Setting(Base):
    __tablename__ = "settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="settings_singleton_check"),
        CheckConstraint(
            "batas_terlambat_menit >= 0",
            name="settings_late_minutes_check",
        ),
        CheckConstraint(
            "fr_mode IN ('endpoint', 'local', 'disabled')",
            name="settings_fr_mode_check",
        ),
    )

    id: Mapped[int] = mapped_column(
        SmallInteger, primary_key=True, default=1, server_default=text("1")
    )
    jam_masuk: Mapped[time] = mapped_column(
        Time, nullable=False, default=time(7, 0), server_default=text("'07:00:00'")
    )
    batas_terlambat_menit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    hari_sekolah: Mapped[list[int]] = mapped_column(
        ARRAY(SmallInteger),
        nullable=False,
        default=lambda: [0, 1, 2, 3, 4],
        server_default=text("'{0,1,2,3,4}'::smallint[]"),
    )
    fr_mode: Mapped[str] = mapped_column(
        Text, nullable=False, default="disabled", server_default=text("'disabled'")
    )
    fr_endpoint_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
