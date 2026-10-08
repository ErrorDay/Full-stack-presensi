"""Attendance operations backed by the Supabase attendance schema."""

import uuid
from datetime import date, datetime, time, timedelta

from database.models import Absensi, Setting, Siswa
from database.session import SessionLocal

STATUS_LIST = ["Tidak Terlambat", "Terlambat", "Izin", "Alpa"]


def _get_settings(db) -> Setting:
    setting = db.query(Setting).filter(Setting.id == 1).first()
    if setting is None:
        setting = Setting(id=1, jam_masuk=time(7, 0), batas_terlambat_menit=0)
    return setting


def hitung_status_otomatis(waktu: time, setting: Setting) -> str:
    cutoff = datetime.combine(
        date.today(), setting.jam_masuk
    ) + timedelta(minutes=setting.batas_terlambat_menit)
    scanned_at = datetime.combine(date.today(), waktu)
    return "Tidak Terlambat" if scanned_at <= cutoff else "Terlambat"


class AttendanceService:
    def __init__(self):
        self.db = SessionLocal()

    def record_attendance(
        self,
        siswa: Siswa,
        status: str | None = None,
        tanggal: date | None = None,
        waktu: time | None = None,
        created_by: uuid.UUID | None = None,
        source: str = "face",
        notes: str | None = None,
    ) -> tuple[Absensi, bool]:
        if status is not None and status not in STATUS_LIST:
            raise ValueError(f"Status presensi tidak valid: {status}")
        if source not in ("face", "manual", "import"):
            raise ValueError(f"Sumber presensi tidak valid: {source}")

        now = datetime.now().astimezone()
        attendance_date = tanggal or now.date()
        checked_at = (
            datetime.combine(attendance_date, waktu).astimezone()
            if waktu is not None
            else now
        )
        setting = _get_settings(self.db)
        if status is None:
            status = hitung_status_otomatis(checked_at.timetz().replace(tzinfo=None), setting)

        existing = (
            self.db.query(Absensi)
            .filter(
                Absensi.student_id == siswa.id,
                Absensi.attendance_date == attendance_date,
            )
            .first()
        )
        if existing:
            existing.status = status
            existing.checked_at = checked_at
            existing.source = source
            existing.notes = notes
            if created_by is not None:
                existing.created_by = created_by
            self.db.commit()
            self.db.refresh(existing)
            return existing, True

        absensi = Absensi(
            id=uuid.uuid4(),
            student_id=siswa.id,
            attendance_date=attendance_date,
            checked_at=checked_at,
            status=status,
            source=source,
            notes=notes,
            created_by=created_by,
        )
        self.db.add(absensi)
        self.db.commit()
        self.db.refresh(absensi)
        return absensi, False

    def process_attendance(
        self, siswa: Siswa, created_by: uuid.UUID | None = None
    ) -> tuple[Absensi, bool]:
        return self.record_attendance(siswa, created_by=created_by, source="face")

    def check_in(self, siswa_id: uuid.UUID):
        siswa = self.db.query(Siswa).filter(Siswa.id == siswa_id).first()
        if siswa is None:
            print("[ERROR] Siswa tidak ditemukan.")
            return None
        return self.process_attendance(siswa)

    def mark_alpa_harian(self, tanggal: date | None = None) -> int:
        attendance_date = tanggal or date.today()
        siswa_list = self.db.query(Siswa).filter(Siswa.status == "Aktif").all()
        count = 0

        for siswa in siswa_list:
            existing = (
                self.db.query(Absensi.id)
                .filter(
                    Absensi.student_id == siswa.id,
                    Absensi.attendance_date == attendance_date,
                )
                .first()
            )
            if existing is None:
                self.db.add(
                    Absensi(
                        id=uuid.uuid4(),
                        student_id=siswa.id,
                        attendance_date=attendance_date,
                        checked_at=datetime.combine(
                            attendance_date, time(23, 59)
                        ).astimezone(),
                        status="Alpa",
                        source="import",
                        notes="Otomatis oleh sistem - tidak melakukan presensi",
                    )
                )
                count += 1

        self.db.commit()
        return count

    def close(self):
        self.db.close()
