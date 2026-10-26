"""
api/dashboard.py
GET /dashboard/stats -- dipanggil Dashboard.jsx (kartu ringkasan +
donut chart distribusi kehadiran hari ini + tabel aktivitas terbaru).

Bentuk response disamakan persis dengan server.py Emergent supaya
frontend tidak perlu diubah sama sekali.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter
from sqlalchemy import func

from database.session import SessionLocal
from database.models import Siswa, Kelas, Absensi

router = APIRouter()

STATUS_LIST = ["Tidak Terlambat", "Terlambat", "Izin", "Alpa"]


def _serialize_recent(a: Absensi, siswa: Siswa, kelas: Kelas) -> dict:
    return {
        "id": str(a.id),
        "student_id": str(a.siswa_id),
        "nisn": siswa.nis or "",
        "name": siswa.nama,
        "class_id": str(siswa.kelas_id),
        "class_name": kelas.nama if kelas else "",
        "date": a.tanggal.isoformat(),
        "time": a.jam_masuk.strftime("%H:%M:%S"),
        "status": a.status,
    }


@router.get("/stats")
def dashboard_stats():
    db = SessionLocal()
    try:
        today = datetime.now().date()

        total_students = db.query(Siswa).filter(Siswa.status == "AKTIF").count()
        total_classes = db.query(Kelas).count()

        records_today = db.query(Absensi).filter(Absensi.tanggal == today).all()
        counts = {s: 0 for s in STATUS_LIST}
        for r in records_today:
            counts[r.status] = counts.get(r.status, 0) + 1

        hadir = counts["Tidak Terlambat"] + counts["Terlambat"]
        sudah = len({r.siswa_id for r in records_today})

        trend = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            recs = db.query(Absensi).filter(Absensi.tanggal == day).all()
            c = {s: 0 for s in STATUS_LIST}
            for r in recs:
                c[r.status] = c.get(r.status, 0) + 1
            trend.append({
                "date": day.isoformat(),
                "label": day.strftime("%d/%m"),
                "Hadir": c["Tidak Terlambat"] + c["Terlambat"],
                "Terlambat": c["Terlambat"],
                "Izin": c["Izin"],
                "Alpa": c["Alpa"],
            })

        recent_rows = (
            db.query(Absensi, Siswa, Kelas)
            .join(Siswa, Absensi.siswa_id == Siswa.id)
            .join(Kelas, Siswa.kelas_id == Kelas.id)
            .order_by(Absensi.tanggal.desc(), Absensi.jam_masuk.desc())
            .limit(8)
            .all()
        )
        recent = [_serialize_recent(a, s, k) for a, s, k in recent_rows]

        return {
            "date": today.isoformat(),
            "total_students": total_students,
            "total_classes": total_classes,
            "hadir": hadir,
            "tidak_terlambat": counts["Tidak Terlambat"],
            "terlambat": counts["Terlambat"],
            "izin": counts["Izin"],
            "alpa": counts["Alpa"],
            "belum_presensi": max(total_students - sudah, 0),
            "trend": trend,
            "recent": recent,
        }

    finally:
        db.close()
