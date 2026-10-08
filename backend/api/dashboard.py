"""Dashboard attendance statistics and recent activity."""

from datetime import date, timedelta

from fastapi import APIRouter

from database.models import Absensi, Kelas, Siswa
from database.session import SessionLocal

router = APIRouter()
STATUS_LIST = ["Tidak Terlambat", "Terlambat", "Izin", "Alpa"]


def _serialize_recent(a: Absensi, siswa: Siswa, kelas: Kelas | None) -> dict:
    return {
        "id": str(a.id),
        "student_id": str(a.student_id),
        "nisn": siswa.nisn,
        "name": siswa.name,
        "class_id": str(siswa.class_id) if siswa.class_id else None,
        "class_name": kelas.name if kelas else "",
        "date": a.attendance_date.isoformat(),
        "time": a.checked_at.strftime("%H:%M:%S"),
        "status": a.status,
    }


@router.get("/stats")
def dashboard_stats():
    db = SessionLocal()
    try:
        today = date.today()
        total_students = db.query(Siswa).filter(Siswa.status == "Aktif").count()
        total_classes = db.query(Kelas).count()

        records_today = (
            db.query(Absensi.status, Absensi.student_id)
            .filter(Absensi.attendance_date == today)
            .all()
        )
        counts = {status: 0 for status in STATUS_LIST}
        for status, _student_id in records_today:
            counts[status] = counts.get(status, 0) + 1
        hadiran_tercatat = len({student_id for _, student_id in records_today})

        trend = []
        first_day = today - timedelta(days=6)
        daily_rows = (
            db.query(Absensi.attendance_date, Absensi.status, Absensi.id)
            .filter(Absensi.attendance_date >= first_day)
            .all()
        )
        by_day: dict[date, dict[str, int]] = {}
        for record_date, status, _record_id in daily_rows:
            counts_for_day = by_day.setdefault(
                record_date, {value: 0 for value in STATUS_LIST}
            )
            counts_for_day[status] = counts_for_day.get(status, 0) + 1

        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            daily_counts = by_day.get(day, {})
            trend.append(
                {
                    "date": day.isoformat(),
                    "label": day.strftime("%d/%m"),
                    "Hadir": daily_counts.get("Tidak Terlambat", 0)
                    + daily_counts.get("Terlambat", 0),
                    "Terlambat": daily_counts.get("Terlambat", 0),
                    "Izin": daily_counts.get("Izin", 0),
                    "Alpa": daily_counts.get("Alpa", 0),
                }
            )

        recent_rows = (
            db.query(Absensi, Siswa, Kelas)
            .join(Siswa, Absensi.student_id == Siswa.id)
            .outerjoin(Kelas, Siswa.class_id == Kelas.id)
            .order_by(Absensi.checked_at.desc())
            .limit(8)
            .all()
        )
        recent = [_serialize_recent(record, siswa, kelas) for record, siswa, kelas in recent_rows]

        return {
            "date": today.isoformat(),
            "total_students": total_students,
            "total_classes": total_classes,
            "hadir": counts["Tidak Terlambat"] + counts["Terlambat"],
            "tidak_terlambat": counts["Tidak Terlambat"],
            "terlambat": counts["Terlambat"],
            "izin": counts["Izin"],
            "alpa": counts["Alpa"],
            "belum_presensi": max(total_students - hadiran_tercatat, 0),
            "trend": trend,
            "recent": recent,
        }
    finally:
        db.close()
