"""
api/settings_web.py
GET/PUT /settings -- dipanggil Pengaturan.jsx.

`hari_libur` (list tanggal) TIDAK disimpan sebagai kolom di tabel
Setting -- itu tetap query/sync ke tabel HariLibur (single source of
truth yang sudah dipakai modules/kalender.py), supaya tidak ada 2
tempat penyimpanan untuk data yang sama.
"""

import json

from fastapi import APIRouter
from pydantic import BaseModel

from database.session import SessionLocal
from database.models import Setting, HariLibur

router = APIRouter()


class SettingsIn(BaseModel):
    jam_masuk: str = "07:00"
    batas_terlambat_menit: int = 10
    hari_sekolah: list[int] = [0, 1, 2, 3, 4]
    hari_libur: list[str] = []
    fr_mode: str = "local"
    fr_endpoint_url: str = ""


def _get_or_create_setting(db) -> Setting:
    setting = db.query(Setting).first()
    if setting is None:
        setting = Setting()
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


def _serialize(setting: Setting, db) -> dict:
    hari_libur = [h.tanggal.isoformat() for h in db.query(HariLibur).order_by(HariLibur.tanggal).all()]
    return {
        "jam_masuk": setting.jam_masuk.strftime("%H:%M"),
        "batas_terlambat_menit": setting.toleransi_menit,
        "hari_sekolah": json.loads(setting.hari_sekolah),
        "hari_libur": hari_libur,
        "fr_mode": setting.fr_mode,
        "fr_endpoint_url": setting.fr_endpoint_url or "",
        "db_name": "PostgreSQL",
    }


@router.get("")
def read_settings():
    db = SessionLocal()
    try:
        setting = _get_or_create_setting(db)
        return _serialize(setting, db)
    finally:
        db.close()


@router.put("")
def update_settings(data: SettingsIn):
    db = SessionLocal()
    try:
        setting = _get_or_create_setting(db)

        jam_h, jam_m = data.jam_masuk.split(":")
        from datetime import time as time_cls
        setting.jam_masuk = time_cls(int(jam_h), int(jam_m))
        setting.toleransi_menit = data.batas_terlambat_menit
        setting.hari_sekolah = json.dumps(sorted(data.hari_sekolah))
        setting.fr_mode = data.fr_mode
        setting.fr_endpoint_url = data.fr_endpoint_url or None

        # sinkronkan tabel HariLibur dengan list yang dikirim frontend
        from datetime import date as date_cls
        existing_dates = {h.tanggal for h in db.query(HariLibur).all()}
        new_dates = {date_cls.fromisoformat(d) for d in data.hari_libur}

        for d in new_dates - existing_dates:
            db.add(HariLibur(tanggal=d, keterangan="Ditambahkan lewat Pengaturan"))

        for d in existing_dates - new_dates:
            db.query(HariLibur).filter(HariLibur.tanggal == d).delete()

        db.commit()
        db.refresh(setting)
        return _serialize(setting, db)
    finally:
        db.close()
