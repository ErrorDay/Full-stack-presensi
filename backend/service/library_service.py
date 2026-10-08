"""Library visit recording and reporting."""

import uuid
from datetime import date, datetime, time, timedelta

from database.models import Kelas, Kunjungan, Siswa
from database.session import SessionLocal


class LibraryService:
    def __init__(self):
        self.db = SessionLocal()

    def record_visit(
        self,
        siswa: Siswa,
        tanggal: date | None = None,
        waktu: time | None = None,
        created_by: uuid.UUID | None = None,
        source: str = "face",
    ) -> tuple[Kunjungan, int]:
        if source not in ("face", "manual"):
            raise ValueError(f"Sumber kunjungan tidak valid: {source}")

        visited_at = (
            datetime.combine(tanggal, waktu).astimezone()
            if tanggal is not None and waktu is not None
            else datetime.now().astimezone()
        )
        kunjungan = Kunjungan(
            id=uuid.uuid4(),
            student_id=siswa.id,
            visited_at=visited_at,
            source=source,
            created_by=created_by,
        )
        self.db.add(kunjungan)
        self.db.commit()
        self.db.refresh(kunjungan)

        day_start = datetime.combine(visited_at.date(), time.min).astimezone()
        next_day = day_start + timedelta(days=1)
        visit_ke = (
            self.db.query(Kunjungan.id)
            .filter(
                Kunjungan.student_id == siswa.id,
                Kunjungan.visited_at >= day_start,
                Kunjungan.visited_at < next_day,
            )
            .count()
        )
        return kunjungan, visit_ke

    def get_recap(
        self,
        start: date,
        end: date,
        class_id: uuid.UUID | None = None,
    ) -> dict:
        start_at = datetime.combine(start, time.min).astimezone()
        end_exclusive = datetime.combine(end + timedelta(days=1), time.min).astimezone()
        query = (
            self.db.query(Kunjungan, Siswa, Kelas)
            .join(Siswa, Kunjungan.student_id == Siswa.id)
            .outerjoin(Kelas, Siswa.class_id == Kelas.id)
            .filter(
                Kunjungan.visited_at >= start_at,
                Kunjungan.visited_at < end_exclusive,
            )
        )
        if class_id is not None:
            query = query.filter(Siswa.class_id == class_id)

        rows = query.all()
        per_student: dict[uuid.UUID, dict] = {}
        daily_students: dict[date, set[uuid.UUID]] = {}
        for visit, siswa, kelas in rows:
            visit_date = visit.visited_at.astimezone().date()
            daily_students.setdefault(visit_date, set()).add(siswa.id)
            row = per_student.setdefault(
                siswa.id,
                {
                    "student_id": str(siswa.id),
                    "nisn": siswa.nisn,
                    "name": siswa.name,
                    "class_name": kelas.name if kelas else "",
                    "visits": 0,
                    "_days": set(),
                },
            )
            row["visits"] += 1
            row["_days"].add(visit_date)

        daily = []
        current = start
        while current <= end:
            daily.append(
                {
                    "date": current.isoformat(),
                    "visitors": len(daily_students.get(current, set())),
                }
            )
            current += timedelta(days=1)

        output_rows = []
        for row in per_student.values():
            row["days"] = len(row.pop("_days"))
            output_rows.append(row)
        output_rows.sort(key=lambda row: (-row["visits"], row["name"]))

        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "total_visits": len(rows),
            "unique_students": len(per_student),
            "daily": daily,
            "rows": output_rows,
        }

    def get_weekly_recap(
        self, tanggal: date, class_id: uuid.UUID | None = None
    ) -> dict:
        monday = tanggal - timedelta(days=tanggal.weekday())
        return self.get_recap(monday, monday + timedelta(days=6), class_id)

    def get_monthly_recap(
        self, tahun: int, bulan: int, class_id: uuid.UUID | None = None
    ) -> dict:
        import calendar

        final_day = calendar.monthrange(tahun, bulan)[1]
        return self.get_recap(date(tahun, bulan, 1), date(tahun, bulan, final_day), class_id)

    def close(self):
        self.db.close()
