# notification_service.py
import os
import smtplib
import ssl
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv


from database.models import Kelas
from database.session import SessionLocal
from service.attendance_service import AttendanceService
from service.report_service import ReportService
from modules.kontak import get_kontak_kelas
from modules.kalender import is_hari_sekolah

load_dotenv()

JAM_CUTOFF = 7
MENIT_CUTOFF = 30

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Sistem Absensi Sekolah")

_scheduler = None


def tandai_alpa_harian(tanggal: date = None):
    """
    Sebelumnya bernama tandai_tidak_hadir_harian() dengan status
    "TIDAK_HADIR" -- sekarang pakai AttendanceService.mark_alpa_harian()
    dengan status "Alpa", sesuai vocabulary baru yang match frontend.
    """
    if tanggal is None:
        tanggal = date.today()

    if not is_hari_sekolah(tanggal):
        print(f"[SKIP] {tanggal} bukan hari sekolah")
        return

    attendance = AttendanceService()
    try:
        jumlah = attendance.mark_alpa_harian(tanggal)
        print(f"[INFO] Penandaan Alpa selesai untuk {tanggal} ({jumlah} siswa)")
    finally:
        attendance.close()


def _kirim_email(ke: str, subjek: str, isi: str) -> bool:
    if not ke:
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
        msg["To"] = ke
        msg["Subject"] = subjek
        msg.attach(MIMEText(isi, "plain"))

        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, ke, msg.as_string())

        print(f"[EMAIL] Terkirim ke {ke}")
        return True
    except Exception as e:
        print(f"[ERROR] Kirim email ke {ke}: {e}")
        return False


def _susun_isi_email(rekap: dict) -> str:
    baris = [
        "Laporan Absensi Harian",
        f"Kelas   : {rekap['kelas']}",
        f"Tanggal : {rekap['tanggal']}",
        "",
    ]

    if rekap["alpa"]:
        baris.append("Alpa (Tidak Hadir):")
        baris += [f"  - {n}" for n in rekap["alpa"]]
    else:
        baris.append("Tidak ada siswa Alpa.")

    if rekap["terlambat"]:
        baris.append("")
        baris.append("Terlambat:")
        baris += [f"  - {n}" for n in rekap["terlambat"]]

    if rekap["izin"]:
        baris.append("")
        baris.append("Izin:")
        baris += [f"  - {n}" for n in rekap["izin"]]

    baris += [
        "",
        f"Total hadir: {rekap['total_hadir']} dari {rekap['total_siswa']} siswa",
        "",
        "Dikirim otomatis oleh Sistem Absensi.",
    ]
    return "\n".join(baris)


def proses_laporan_harian(kelas_list: list = None):
    tanggal = date.today()

    if not is_hari_sekolah(tanggal):
        print(f"[SKIP] {tanggal} bukan hari sekolah, laporan tidak dikirim")
        return

    tandai_alpa_harian(tanggal)

    report = ReportService()
    db = SessionLocal()
    try:
        if kelas_list is None:
            kelas_list = [k.nama for k in db.query(Kelas).all()]

        for kelas in kelas_list:
            rekap = report.get_rekap_harian(kelas, tanggal)
            isi_email = _susun_isi_email(rekap)
            kontak = get_kontak_kelas(kelas)

            if not kontak:
                print(f"[WARNING] Kontak untuk {kelas} belum diset")
                continue

            subjek = f"Laporan Absensi {kelas} - {rekap['tanggal']}"

            _kirim_email(kontak.get("walas_email"), subjek, isi_email)
            _kirim_email(kontak.get("aswalas_email"), subjek, isi_email)

    finally:
        db.close()
        report.close()


def start_scheduler():
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        print("[SCHEDULER] Sudah berjalan")
        return

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        func=proses_laporan_harian,
        trigger="cron",
        hour=JAM_CUTOFF,
        minute=MENIT_CUTOFF,
        id="laporan_harian",
        replace_existing=True,
    )
    _scheduler.start()
    print(f"[SCHEDULER] Aktif - laporan harian jam {JAM_CUTOFF:02d}:{MENIT_CUTOFF:02d}")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        print("[SCHEDULER] Dihentikan")
