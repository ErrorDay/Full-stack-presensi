"""Read and update singleton application settings."""

from datetime import date, time
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from database.models import HariLibur, Setting
from database.session import SessionLocal

router = APIRouter()


class SettingsIn(BaseModel):
    jam_masuk: str = "07:00"
    batas_terlambat_menit: int = Field(default=0, ge=0)
    hari_sekolah: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    hari_libur: list[str] = Field(default_factory=list)
    fr_mode: Literal["endpoint", "local", "disabled"] = "disabled"
    fr_endpoint_url: str | None = None

    @field_validator("hari_sekolah")
    @classmethod
    def validate_school_days(cls, values: list[int]) -> list[int]:
        if any(day < 0 or day > 6 for day in values):
            raise ValueError("hari_sekolah hanya menerima nilai 0 sampai 6")
        return sorted(set(values))

    @field_validator("jam_masuk")
    @classmethod
    def validate_start_time(cls, value: str) -> str:
        try:
            time.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("jam_masuk harus berupa waktu HH:MM atau HH:MM:SS") from exc
        return value


def _get_or_create_setting(db) -> Setting:
    setting = db.query(Setting).filter(Setting.id == 1).first()
    if setting is None:
        setting = Setting(id=1)
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


def _serialize(setting: Setting, db) -> dict:
    hari_libur = [
        item.tanggal.isoformat()
        for item in db.query(HariLibur).order_by(HariLibur.tanggal).all()
    ]
    return {
        "jam_masuk": setting.jam_masuk.strftime("%H:%M"),
        "batas_terlambat_menit": setting.batas_terlambat_menit,
        "hari_sekolah": list(setting.hari_sekolah),
        "hari_libur": hari_libur,
        "fr_mode": setting.fr_mode,
        "fr_endpoint_url": setting.fr_endpoint_url or "",
        "db_name": "PostgreSQL",
    }


@router.get("")
def read_settings():
    db = SessionLocal()
    try:
        return _serialize(_get_or_create_setting(db), db)
    finally:
        db.close()


@router.put("")
def update_settings(data: SettingsIn):
    db = SessionLocal()
    try:
        setting = _get_or_create_setting(db)
        setting.jam_masuk = time.fromisoformat(data.jam_masuk)
        setting.batas_terlambat_menit = data.batas_terlambat_menit
        setting.hari_sekolah = data.hari_sekolah
        setting.fr_mode = data.fr_mode
        setting.fr_endpoint_url = data.fr_endpoint_url or None

        try:
            new_dates = {date.fromisoformat(value) for value in data.hari_libur}
        except ValueError as exc:
            raise HTTPException(422, "Format hari_libur harus YYYY-MM-DD") from exc

        existing_dates = {item.tanggal for item in db.query(HariLibur).all()}
        for day in new_dates - existing_dates:
            db.add(HariLibur(tanggal=day, keterangan="Ditambahkan lewat Pengaturan"))
        for day in existing_dates - new_dates:
            db.query(HariLibur).filter(HariLibur.tanggal == day).delete()

        db.commit()
        db.refresh(setting)
        return _serialize(setting, db)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
