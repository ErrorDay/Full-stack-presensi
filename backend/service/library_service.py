"""
service/library_service.py

Service untuk fitur baru "Kunjungan Perpustakaan" -- terpisah dari
AttendanceService karena semantiknya beda: satu siswa BOLEH tercatat
berkali-kali dalam satu hari, tetapi hanya setelah cooldown satu jam
sejak kunjungan terakhirnya.
"""

from datetime import date, datetime, time, timedelta

from database.models import Kunjungan, Siswa, Kelas
from database.session import SessionLocal


class LibraryService:

    COOLDOWN = timedelta(hours=1)

    def __init__(self):
        self.db = SessionLocal()

    def record_visit(
        self,
        siswa: Siswa,
        tanggal: date | None = None,
        waktu: time | None = None,
    ) -> tuple[Kunjungan | None, int]:
        """
        Catat kunjungan baru jika siswa tidak berkunjung dalam satu jam terakhir.
        Return (None, 0) jika siswa masih dalam masa cooldown.
        Return: (Kunjungan, visit_ke) -- visit_ke = urutan kunjungan
        siswa ini pada hari itu (1 = kunjungan pertama hari itu, dst).
        """
        now = datetime.now()
        tanggal = tanggal or now.date()
        waktu = waktu or now.time()

        last_visit = (
            self.db.query(Kunjungan)
            .filter(Kunjungan.siswa_id == siswa.id)
            .order_by(Kunjungan.tanggal.desc(), Kunjungan.waktu.desc())
            .first()
        )
        if last_visit:
            last_visit_at = datetime.combine(last_visit.tanggal, last_visit.waktu)
            if datetime.combine(tanggal, waktu) - last_visit_at < self.COOLDOWN:
                return None, 0

        kunjungan = Kunjungan(siswa_id=siswa.id, tanggal=tanggal, waktu=waktu)
        self.db.add(kunjungan)
        self.db.commit()
        self.db.refresh(kunjungan)

        visit_ke = (
            self.db.query(Kunjungan)
            .filter(Kunjungan.siswa_id == siswa.id, Kunjungan.tanggal == tanggal)
            .count()
        )

        return kunjungan, visit_ke

    def get_recap(self, start: date, end: date, kelas_id: int | None = None) -> dict:
        """
        Rekap kunjungan dalam rentang tanggal [start, end] inklusif.
        Dipakai untuk rekap mingguan (Senin-Minggu) maupun bulanan.
        """
        query = (
            self.db.query(Kunjungan, Siswa, Kelas)
            .join(Siswa, Kunjungan.siswa_id == Siswa.id)
            .join(Kelas, Siswa.kelas_id == Kelas.id)
            .filter(Kunjungan.tanggal >= start, Kunjungan.tanggal <= end)
        )

        if kelas_id:
            query = query.filter(Siswa.kelas_id == kelas_id)

        rows = query.all()

        total_visits = len(rows)
        unique_students = len({k.siswa_id for k, s, kls in rows})

        # rekap harian (dipakai tampilan "Rekap Pekan")
        daily = []
        cur = start
        while cur <= end:
            visitors = len({k.siswa_id for k, s, kls in rows if k.tanggal == cur})
            daily.append({"date": cur.isoformat(), "visitors": visitors})
            cur += timedelta(days=1)

        # rekap per siswa
        per_siswa = {}
        for k, s, kls in rows:
            if s.id not in per_siswa:
                per_siswa[s.id] = {
                    "student_id": str(s.id),
                    "nisn": s.nis or "",
                    "name": s.nama,
                    "class_name": kls.nama,
                    "visits": 0,
                    "_hari": set(),
                }
            per_siswa[s.id]["visits"] += 1
            per_siswa[s.id]["_hari"].add(k.tanggal)

        rows_out = []
        for r in per_siswa.values():
            r["days"] = len(r.pop("_hari"))
            rows_out.append(r)

        rows_out.sort(key=lambda r: r["visits"], reverse=True)

        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "total_visits": total_visits,
            "unique_students": unique_students,
            "daily": daily,
            "rows": rows_out,
        }

    def get_weekly_recap(self, tanggal: date, kelas_id: int | None = None) -> dict:
        """Senin-Minggu dari minggu yang mengandung `tanggal`."""
        senin = tanggal - timedelta(days=tanggal.weekday())
        minggu = senin + timedelta(days=6)
        return self.get_recap(senin, minggu, kelas_id)

    def get_monthly_recap(self, tahun: int, bulan: int, kelas_id: int | None = None) -> dict:
        import calendar
        hari_terakhir = calendar.monthrange(tahun, bulan)[1]
        start = date(tahun, bulan, 1)
        end = date(tahun, bulan, hari_terakhir)
        return self.get_recap(start, end, kelas_id)

    def close(self):
        self.db.close()
