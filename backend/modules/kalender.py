# kalender.py
import json
from datetime import date
from database.models import HariLibur, Setting
from database.session import SessionLocal


def is_hari_sekolah(tanggal: date = None) -> bool:
    """
    False jika:
      - Hari dalam minggu tidak termasuk Setting.hari_sekolah
        (default [0,1,2,3,4] = Senin-Jumat; dulu hardcode Sabtu/Minggu,
        sekarang configurable lewat halaman Pengaturan frontend)
      - Tanggal ada di tabel HariLibur (tetap single source of truth
        untuk tanggal libur spesifik, bukan disimpan di Setting)
    """
    if tanggal is None:
        tanggal = date.today()

    db = SessionLocal()
    try:
        setting = db.query(Setting).first()
        hari_sekolah = (
            json.loads(setting.hari_sekolah)
            if setting else [0, 1, 2, 3, 4]
        )

        if tanggal.weekday() not in hari_sekolah:
            return False

        libur = (
            db.query(HariLibur)
            .filter(HariLibur.tanggal == tanggal)
            .first()
        )
        return libur is None
    finally:
        db.close()


def tambah_hari_libur(tanggal: date, keterangan: str = "") -> bool:
    db = SessionLocal()
    try:
        db.add(HariLibur(tanggal=tanggal, keterangan=keterangan))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"[ERROR] tambah_hari_libur: {e}")
        return False
    finally:
        db.close()
