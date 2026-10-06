"""
api/export.py
GET /export/daily.{csv,pdf}, GET /export/monthly.{csv,pdf}
-- dipanggil tombol Download di Presensi.jsx.

Styling PDF disamakan dengan pdf_response() di server.py Emergent
(header biru #1D4ED8, grid tipis) supaya hasilnya konsisten dengan
desain aslinya.
"""

import io
import csv
import calendar
from datetime import date as date_cls

from fastapi import APIRouter, Query, Response

from api.attendance_web import list_attendance
from service.report_service import ReportService
from service.library_service import LibraryService

router = APIRouter()


def _csv_response(rows: list, header: list, filename: str) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _pdf_response(title: str, subtitle: str, header: list, rows: list, filename: str) -> Response:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    elems = [Paragraph(title, styles["Title"]), Paragraph(subtitle, styles["Normal"]), Spacer(1, 8 * mm)]

    table = Table([header] + rows, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elems.append(table)
    doc.build(elems)

    return Response(
        buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _filter_label(class_id: str | None) -> str:
    if not class_id:
        return "Semua Kelas"
    from database.session import SessionLocal
    from database.models import Kelas
    db = SessionLocal()
    try:
        kelas = db.query(Kelas).filter(Kelas.id == int(class_id)).first()
        return kelas.nama if kelas else "Semua Kelas"
    finally:
        db.close()


@router.get("/daily.csv")
def export_daily_csv(date: str = Query(...), class_id: str | None = None, status: str | None = None):
    recs = list_attendance(date=date, class_id=class_id, status=status)
    rows = [[r["name"], r["nisn"], r["class_name"], r["date"], r["time"], r["status"]] for r in recs]
    return _csv_response(rows, ["Nama", "NIS/NISN", "Kelas", "Tanggal", "Jam", "Status"],
                         f"rekap_harian_{date}.csv")


@router.get("/daily.pdf")
def export_daily_pdf(date: str = Query(...), class_id: str | None = None, status: str | None = None):
    recs = list_attendance(date=date, class_id=class_id, status=status)
    recs = sorted(recs, key=lambda r: (r["class_name"], r["name"]))
    rows = [[r["name"], r["nisn"], r["class_name"], r["date"], r["time"], r["status"]] for r in recs]
    label = _filter_label(class_id)
    return _pdf_response(
        "LAPORAN PRESENSI HARIAN",
        f"Tanggal: {date} | Kelas: {label} | Status: {status or 'Semua'}",
        ["Nama", "NIS/NISN", "Kelas", "Tanggal", "Jam", "Status"], rows,
        f"rekap_harian_{date}.pdf",
    )


@router.get("/monthly.csv")
def export_monthly_csv(year: int = Query(...), month: int = Query(...), class_id: str | None = None):
    report = ReportService()
    try:
        from database.session import SessionLocal
        from database.models import Kelas
        kelas_nama = None
        if class_id:
            db = SessionLocal()
            k = db.query(Kelas).filter(Kelas.id == int(class_id)).first()
            kelas_nama = k.nama if k else None
            db.close()

        data = report.get_rekap_bulanan(year, month, kelas_nama)
        rows = [[r["name"], r["nisn"], r["class_name"], r["hadir"], r["terlambat"], r["izin"], r["alpa"], r["total"]]
                for r in data]
        return _csv_response(
            rows, ["Nama", "NIS/NISN", "Kelas", "Hadir", "Terlambat", "Izin", "Alpa", "Total Presensi"],
            f"rekap_bulanan_{year}-{month:02d}.csv",
        )
    finally:
        report.close()


@router.get("/monthly.pdf")
def export_monthly_pdf(year: int = Query(...), month: int = Query(...), class_id: str | None = None):
    report = ReportService()
    try:
        from database.session import SessionLocal
        from database.models import Kelas
        from modules.kalender import is_hari_sekolah
        from datetime import date as date_cls

        kelas_nama = None
        if class_id:
            db = SessionLocal()
            k = db.query(Kelas).filter(Kelas.id == int(class_id)).first()
            kelas_nama = k.nama if k else None
            db.close()

        data = report.get_rekap_bulanan(year, month, kelas_nama)
        rows = [[r["name"], r["nisn"], r["class_name"], r["hadir"], r["terlambat"], r["izin"], r["alpa"], r["total"]]
                for r in data]

        days_in_month = calendar.monthrange(year, month)[1]
        hari_sekolah = sum(1 for d in range(1, days_in_month + 1) if is_hari_sekolah(date_cls(year, month, d)))

        label = _filter_label(class_id)
        bulan_nama = calendar.month_name[month]
        return _pdf_response(
            "LAPORAN PRESENSI BULANAN",
            f"Periode: {bulan_nama} {year} | Kelas: {label} | Hari sekolah: {hari_sekolah} hari",
            ["Nama", "NIS/NISN", "Kelas", "Hadir", "Terlambat", "Izin", "Alpa", "Total"], rows,
            f"rekap_bulanan_{year}-{month:02d}.pdf",
        )
    finally:
        report.close()


def _get_library_recap(type: str, date: str | None, month: int | None, year: int | None, class_id: str | None):
    library = LibraryService()
    try:
        kelas_id = int(class_id) if class_id else None
        if type == "weekly":
            return library.get_weekly_recap(date_cls.fromisoformat(date), kelas_id)
        return library.get_monthly_recap(year, month, kelas_id)
    finally:
        library.close()


@router.get("/library.csv")
def export_library_csv(
    type: str = Query(...),
    date: str | None = None,
    month: int | None = None,
    year: int | None = None,
    class_id: str | None = None,
):
    data = _get_library_recap(type, date, month, year, class_id)
    rows = [[r["name"], r["nisn"], r["class_name"], r["visits"], r["days"]] for r in data["rows"]]
    nama_file = f"kunjungan_perpustakaan_{data['start']}_{data['end']}.csv"
    return _csv_response(rows, ["Nama", "NIS/NISN", "Kelas", "Jumlah Kunjungan", "Hari Berbeda"], nama_file)


@router.get("/library.pdf")
def export_library_pdf(
    type: str = Query(...),
    date: str | None = None,
    month: int | None = None,
    year: int | None = None,
    class_id: str | None = None,
):
    data = _get_library_recap(type, date, month, year, class_id)
    rows = [[r["name"], r["nisn"], r["class_name"], r["visits"], r["days"]] for r in data["rows"]]
    label = _filter_label(class_id)
    judul = "LAPORAN KUNJUNGAN PERPUSTAKAAN"
    subjudul = (
        f"Periode: {data['start']} s.d. {data['end']} | Kelas: {label} | "
        f"Total kunjungan: {data['total_visits']} | Pengunjung unik: {data['unique_students']}"
    )
    nama_file = f"kunjungan_perpustakaan_{data['start']}_{data['end']}.pdf"
    return _pdf_response(
        judul, subjudul,
        ["Nama", "NIS/NISN", "Kelas", "Jumlah Kunjungan", "Hari Berbeda"], rows,
        nama_file,
    )
