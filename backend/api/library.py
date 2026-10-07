"""
api/library.py
GET /library/recap -- dipanggil Presensi.jsx (mode "Kunjungan Perpustakaan").

Query params:
  type=weekly&date=YYYY-MM-DD&class_id=...
  type=monthly&month=M&year=YYYY&class_id=...
"""

from datetime import date as date_cls

from fastapi import APIRouter, HTTPException, Query

from service.library_service import LibraryService

router = APIRouter()


@router.get("/recap")
def library_recap(
    type: str = Query(...),
    date: str | None = None,
    month: int | None = None,
    year: int | None = None,
    class_id: str | None = None,
):
    library = LibraryService()
    try:
        kelas_id = int(class_id) if class_id else None

        if type == "weekly":
            if not date:
                raise HTTPException(400, "Parameter 'date' diperlukan untuk type=weekly")
            return library.get_weekly_recap(date_cls.fromisoformat(date), kelas_id)

        if type == "monthly":
            if not month or not year:
                raise HTTPException(400, "Parameter 'month' dan 'year' diperlukan untuk type=monthly")
            return library.get_monthly_recap(year, month, kelas_id)

        raise HTTPException(400, "type harus 'weekly' atau 'monthly'")

    finally:
        library.close()
