"""
service/attendance_service.py

DIROMBAK dari versi check-in/check-out lama, sesuai keputusan:
- Scan sebelum batas waktu (jam_masuk + toleransi_menit) -> "Tidak Terlambat"
- Scan setelah batas waktu -> "Terlambat"
- Tidak ada scan sama sekali sampai akhir hari -> "Alpa" (lihat mark_alpa_harian)
- Walas bisa override manual jadi "Izin" (atau status lain) kapan saja

Satu siswa maksimal 1 baris Absensi per hari (upsert by siswa_id+tanggal),
mengikuti kontrak endpoint POST /api/attendance milik frontend React.
"""

from datetime import date, datetime, time, timedelta

from database.models import Absensi, Siswa, Setting
from database.session import SessionLocal

STATUS_LIST = ["Tidak Terlambat", "Terlambat", "Izin", "Alpa"]


def _get_settings(db) -> Setting:
    setting = db.query(Setting).first()
    if setting is None:
        # fallback aman kalau tabel settings belum pernah diisi
        setting = Setting(jam_masuk=time(7, 0), toleransi_menit=10)
    return setting


def hitung_status_otomatis(waktu: time, setting: Setting) -> str:
    """
    Sama seperti auto_status() di server.py Emergent:
    Tidak Terlambat jika waktu <= jam_masuk + toleransi_menit, selain itu Terlambat.
    """
    hari_ini = date.today()
    batas = datetime.combine(hari_ini, setting.jam_masuk) + timedelta(minutes=setting.toleransi_menit)
    waktu_dt = datetime.combine(hari_ini, waktu)

    return "Tidak Terlambat" if waktu_dt <= batas else "Terlambat"


class AttendanceService:

    def __init__(self):
        self.db = SessionLocal()

    def record_attendance(
        self,
        siswa: Siswa,
        status: str | None = None,
        tanggal: date | None = None,
        waktu: time | None = None,
    ) -> tuple[Absensi, bool]:
        """
        Upsert 1 baris Absensi untuk siswa pada tanggal tsb.

        status=None -> dihitung otomatis (Tidak Terlambat / Terlambat)
                        berdasarkan waktu scan vs Setting.
        status diisi eksplisit -> override manual (mis. "Izin" oleh walas,
                        atau "Alpa" oleh mark_alpa_harian).

        Return: (Absensi, updated) -- updated=True kalau baris hari itu
        sudah ada sebelumnya dan di-update, False kalau baru dibuat.
        """

        setting = _get_settings(self.db)
        now = datetime.now()

        tanggal = tanggal or now.date()
        waktu = waktu or now.time()

        if status is None:
            status = hitung_status_otomatis(waktu, setting)

        existing = (
            self.db.query(Absensi)
            .filter(
                Absensi.siswa_id == siswa.id,
                Absensi.tanggal == tanggal,
            )
            .first()
        )

        if existing:
            existing.status = status
            existing.jam_masuk = waktu
            self.db.commit()
            self.db.refresh(existing)
            return existing, True

        absensi = Absensi(
            siswa_id=siswa.id,
            tanggal=tanggal,
            jam_masuk=waktu,
            status=status,
            keterangan=None,
        )
        self.db.add(absensi)
        self.db.commit()
        self.db.refresh(absensi)
        return absensi, False

    def process_attendance(self, siswa: Siswa) -> tuple[Absensi, bool]:
        """
        Dipanggil saat siswa scan wajah -- status dihitung otomatis
        (Tidak Terlambat / Terlambat). Setara dengan alur lama
        process_attendance(), tapi tanpa konsep check-out.
        """
        return self.record_attendance(siswa, status=None)

    def check_in(self, siswa_id: int):
        """Kompatibilitas dengan kode lama (dipakai tes_attendance.py)."""
        siswa = self.db.query(Siswa).filter(Siswa.id == siswa_id).first()
        if siswa is None:
            print("[ERROR] Siswa tidak ditemukan.")
            return None
        return self.process_attendance(siswa)

    def mark_alpa_harian(self, tanggal: date | None = None) -> int:
        """
        Tandai "Alpa" untuk semua siswa aktif yang belum ada baris
        Absensi pada tanggal tsb. Dipanggil oleh scheduler harian
        (notification_service.py), menggantikan tandai_tidak_hadir_harian
        versi lama yang pakai status "TIDAK_HADIR".

        Return: jumlah siswa yang ditandai Alpa.
        """
        tanggal = tanggal or date.today()

        siswa_list = self.db.query(Siswa).filter(Siswa.status == "AKTIF").all()
        count = 0

        for siswa in siswa_list:
            sudah_ada = (
                self.db.query(Absensi)
                .filter(Absensi.siswa_id == siswa.id, Absensi.tanggal == tanggal)
                .first()
            )
            if sudah_ada is None:
                self.db.add(Absensi(
                    siswa_id=siswa.id,
                    tanggal=tanggal,
                    jam_masuk=time(23, 59),
                    status="Alpa",
                    keterangan="Otomatis oleh sistem - tidak melakukan presensi",
                ))
                count += 1

        self.db.commit()
        return count

    def close(self):
        self.db.close()
