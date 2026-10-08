"""Attendance summaries and exports for the Supabase schema."""

import uuid
from datetime import date

import pandas as pd
from sqlalchemy import distinct, extract, func

from database.models import Absensi, Kelas, Siswa
from database.session import SessionLocal

STATUS_LIST = ["Tidak Terlambat", "Terlambat", "Izin", "Alpa"]


class ReportService:
    def __init__(self):
        self.db = SessionLocal()

    def get_bulan_tersedia(self) -> list[str]:
        rows = (
            self.db.query(
                extract("year", Absensi.attendance_date),
                extract("month", Absensi.attendance_date),
            )
            .distinct()
            .all()
        )
        return sorted(
            {f"{int(year):04d}-{int(month):02d}" for year, month in rows},
            reverse=True,
        )

    def get_kelas_tersedia(self, bulan: str) -> list[str]:
        tahun, month = map(int, bulan.split("-"))
        rows = (
            self.db.query(distinct(Kelas.name))
            .join(Siswa, Siswa.class_id == Kelas.id)
            .join(Absensi, Absensi.student_id == Siswa.id)
            .filter(
                extract("year", Absensi.attendance_date) == tahun,
                extract("month", Absensi.attendance_date) == month,
            )
            .all()
        )
        return sorted(name for (name,) in rows if name is not None)

    def get_rekap_harian(
        self, kelas_nama: str, tanggal: date | None = None
    ) -> dict:
        tanggal = tanggal or date.today()
        siswa_kelas = (
            self.db.query(Siswa)
            .join(Kelas, Siswa.class_id == Kelas.id)
            .filter(Kelas.name == kelas_nama)
            .all()
        )
        attendance = (
            self.db.query(Absensi)
            .join(Siswa, Absensi.student_id == Siswa.id)
            .join(Kelas, Siswa.class_id == Kelas.id)
            .filter(
                Kelas.name == kelas_nama,
                Absensi.attendance_date == tanggal,
            )
            .all()
        )
        status_by_student = {record.student_id: record.status for record in attendance}
        alpa = [
            student.name
            for student in siswa_kelas
            if status_by_student.get(student.id, "Alpa") == "Alpa"
        ]
        terlambat = [
            student.name
            for student in siswa_kelas
            if status_by_student.get(student.id) == "Terlambat"
        ]
        izin = [
            student.name
            for student in siswa_kelas
            if status_by_student.get(student.id) == "Izin"
        ]
        total_hadir = sum(
            status_by_student.get(student.id) in ("Tidak Terlambat", "Terlambat")
            for student in siswa_kelas
        )
        return {
            "kelas": kelas_nama,
            "tanggal": tanggal.isoformat(),
            "alpa": alpa,
            "terlambat": terlambat,
            "izin": izin,
            "total_siswa": len(siswa_kelas),
            "total_hadir": total_hadir,
        }

    def get_rekap_bulanan(
        self,
        tahun: int,
        bulan: int,
        class_id: uuid.UUID | None = None,
    ) -> list[dict]:
        query = (
            self.db.query(
                Siswa.id.label("student_id"),
                Siswa.nisn,
                Siswa.name,
                Kelas.name.label("class_name"),
                Absensi.status,
                func.count(Absensi.id).label("jumlah"),
            )
            .join(Absensi, Absensi.student_id == Siswa.id)
            .outerjoin(Kelas, Siswa.class_id == Kelas.id)
            .filter(
                extract("year", Absensi.attendance_date) == tahun,
                extract("month", Absensi.attendance_date) == bulan,
            )
        )
        if class_id is not None:
            query = query.filter(Siswa.class_id == class_id)
        rows = (
            query.group_by(
                Siswa.id,
                Siswa.nisn,
                Siswa.name,
                Kelas.name,
                Absensi.status,
            )
            .all()
        )

        result: dict[uuid.UUID, dict] = {}
        status_key = {
            "Tidak Terlambat": "hadir",
            "Terlambat": "terlambat",
            "Izin": "izin",
            "Alpa": "alpa",
        }
        for student_id, nisn, name, class_name, status, count in rows:
            student = result.setdefault(
                student_id,
                {
                    "student_id": str(student_id),
                    "nisn": nisn,
                    "name": name,
                    "class_name": class_name or "",
                    "hadir": 0,
                    "terlambat": 0,
                    "izin": 0,
                    "alpa": 0,
                    "total": 0,
                },
            )
            key = status_key.get(status)
            if key:
                student[key] = count
            student["total"] += count
        return list(result.values())

    def export_excel(self, bulan: str, output_file: str):
        tahun, month = map(int, bulan.split("-"))
        data = self.get_rekap_bulanan(tahun, month)
        df = pd.DataFrame(data)

        with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
            sheet_name = f"Rekap_{bulan}"[:31]
            if df.empty:
                pd.DataFrame(
                    columns=[
                        "name",
                        "class_name",
                        "hadir",
                        "terlambat",
                        "izin",
                        "alpa",
                        "total",
                    ]
                ).to_excel(writer, sheet_name=sheet_name, index=False)
            else:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                for class_name in sorted(df["class_name"].fillna("").unique()):
                    if not class_name:
                        continue
                    df[df["class_name"] == class_name].to_excel(
                        writer, sheet_name=class_name[:31], index=False
                    )
        return output_file

    def close(self):
        self.db.close()
