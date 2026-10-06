# report_service.py
from datetime import date

from sqlalchemy import extract, func, distinct

from database.models import Absensi, Siswa, Kelas
from database.session import SessionLocal

STATUS_LIST = ["Tidak Terlambat", "Terlambat", "Izin", "Alpa"]


class ReportService:

    def __init__(self):
        self.db = SessionLocal()

    # =====================================
    # BULAN & KELAS TERSEDIA
    # =====================================
    def get_bulan_tersedia(self) -> list:
        """Return list bulan (format 'YYYY-MM') yang ada datanya, terbaru dulu."""
        rows = (
            self.db.query(
                extract("year", Absensi.tanggal),
                extract("month", Absensi.tanggal),
            )
            .distinct()
            .all()
        )
        bulan = sorted(
            {f"{int(y):04d}-{int(m):02d}" for y, m in rows},
            reverse=True,
        )
        return bulan

    def get_kelas_tersedia(self, bulan: str) -> list:
        """Return list nama kelas yang ada datanya di bulan tsb."""
        tahun, bln = map(int, bulan.split("-"))
        rows = (
            self.db.query(distinct(Kelas.nama))
            .join(Siswa, Siswa.kelas_id == Kelas.id)
            .join(Absensi, Absensi.siswa_id == Siswa.id)
            .filter(
                extract("year", Absensi.tanggal) == tahun,
                extract("month", Absensi.tanggal) == bln,
            )
            .all()
        )
        return sorted([r[0] for r in rows])

    # =====================================
    # REKAP HARIAN
    # =====================================
    def get_rekap_harian(self, kelas_nama: str, tanggal: date = None):
        if tanggal is None:
            tanggal = date.today()

        siswa_kelas = (
            self.db.query(Siswa)
            .join(Kelas, Siswa.kelas_id == Kelas.id)
            .filter(Kelas.nama == kelas_nama)
            .all()
        )

        absensi_hari_ini = (
            self.db.query(Absensi)
            .join(Siswa, Absensi.siswa_id == Siswa.id)
            .join(Kelas, Siswa.kelas_id == Kelas.id)
            .filter(Kelas.nama == kelas_nama, Absensi.tanggal == tanggal)
            .all()
        )

        status_map = {a.siswa_id: a.status for a in absensi_hari_ini}

        alpa = [
            s.nama for s in siswa_kelas
            if status_map.get(s.id, "Alpa") == "Alpa"
        ]
        terlambat = [
            s.nama for s in siswa_kelas
            if status_map.get(s.id) == "Terlambat"
        ]
        izin = [
            s.nama for s in siswa_kelas
            if status_map.get(s.id) == "Izin"
        ]
        total_hadir = sum(
            1 for s in siswa_kelas
            if status_map.get(s.id) in ("Tidak Terlambat", "Terlambat")
        )

        return {
            "kelas": kelas_nama,
            "tanggal": tanggal.strftime("%Y-%m-%d"),
            "alpa": alpa,
            "terlambat": terlambat,
            "izin": izin,
            "total_siswa": len(siswa_kelas),
            "total_hadir": total_hadir,
        }

    # =====================================
    # REKAP BULANAN
    # =====================================
    def get_rekap_bulanan(self, tahun: int, bulan: int, kelas_nama: str = None):
        query = (
            self.db.query(
                Siswa.id, Siswa.nis, Siswa.nama, Kelas.nama.label("kelas"),
                Absensi.status, func.count(Absensi.id).label("jumlah"),
            )
            .join(Absensi, Absensi.siswa_id == Siswa.id)
            .join(Kelas, Siswa.kelas_id == Kelas.id)
            .filter(
                extract("year", Absensi.tanggal) == tahun,
                extract("month", Absensi.tanggal) == bulan,
            )
        )

        if kelas_nama:
            query = query.filter(Kelas.nama == kelas_nama)

        rows = query.group_by(Siswa.id, Siswa.nis, Siswa.nama, Kelas.nama, Absensi.status).all()

        hasil = {}
        for siswa_id, nis, nama, kelas, status, jumlah in rows:
            if siswa_id not in hasil:
                hasil[siswa_id] = {
                    "student_id": str(siswa_id),
                    "nisn": nis or "",
                    "name": nama,
                    "class_name": kelas,
                    "hadir": 0,       # = Tidak Terlambat, sesuai kontrak frontend
                    "terlambat": 0,
                    "izin": 0,
                    "alpa": 0,
                    "total": 0,
                }
            key = {
                "Tidak Terlambat": "hadir",
                "Terlambat": "terlambat",
                "Izin": "izin",
                "Alpa": "alpa",
            }.get(status)
            if key:
                hasil[siswa_id][key] = jumlah
            hasil[siswa_id]["total"] += jumlah

        return list(hasil.values())

    # =====================================
    # EXPORT EXCEL
    # =====================================
    def export_excel(self, bulan: str, output_file: str):
        """Export semua kelas untuk bulan tsb ke Excel multi-sheet."""
        import pandas as pd

        tahun, bln = map(int, bulan.split("-"))
        data = self.get_rekap_bulanan(tahun, bln)

        df = pd.DataFrame(data)

        with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
            nama_sheet_rekap = f"Rekap_{bulan}"[:31]

            if not df.empty:
                df.to_excel(writer, sheet_name=nama_sheet_rekap, index=False)
                for kelas in sorted(df["class_name"].unique()):
                    df_kelas = df[df["class_name"] == kelas]
                    df_kelas.to_excel(writer, sheet_name=kelas[:31], index=False)
            else:
                pd.DataFrame(
                    columns=["name", "class_name", "hadir", "terlambat", "izin", "alpa", "total"]
                ).to_excel(writer, sheet_name=nama_sheet_rekap, index=False)

        return output_file

    def close(self):
        self.db.close()
