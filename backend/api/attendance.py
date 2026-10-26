"""
api/attendance.py
Endpoint presensi — versi web dari CameraThread.run() di tes_kamera.py.

Beda utama dari versi PyQt5:
- Di sana loop kamera + recognize + anti-spoof + attendance semua
  jalan di satu thread yang hidup terus.
- Di sini, browser yang mengambil snapshot tiap beberapa detik dan
  mengirim satu frame per request. Supaya tetap murah, RecognitionService
  & AntiSpoofService TIDAK dibuat ulang tiap request — instance-nya
  dibuat sekali saat startup dan disimpan di app.state (lihat main.py).
- Cooldown 10 detik per nama (persis seperti tes_kamera.py) disimpan
  di app.state.attendance_last_scan supaya tidak insert Absensi
  berkali-kali dalam rentang waktu singkat.
"""

import time

# WAJIB diimpor sebelum modul lain yang menyentuh InsightFace,
# supaya tidak ikut menarik dependency torch yang bermasalah.
import modules._patch_torch_deps  # noqa: F401

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from service.attendance_service import AttendanceService
from api.utils import decode_base64_image

router = APIRouter()

COOLDOWN_DETIK = 10  # sama seperti tes_kamera.py


class ScanRequest(BaseModel):
    image: str  # base64, dengan atau tanpa prefix "data:image/jpeg;base64,"


class FaceResult(BaseModel):
    nama: str | None
    siswa_id: int | None
    similarity: float
    confidence: float
    is_real: bool
    spoof_score: float
    bbox: tuple[int, int, int, int]
    status: str | None  # CHECK_IN / CHECK_OUT / ALREADY / None (tidak dikenali / fake)


@router.post("/scan", response_model=list[FaceResult])
def scan_presensi(payload: ScanRequest, request: Request):
    """
    Terima 1 frame dari browser (base64), jalankan pipeline lengkap:
    recognize -> anti-spoof -> attendance (dengan cooldown).

    Frontend (static/js/presensi.js, dibuat di tahap 4) memanggil ini
    tiap 1-2 detik dari elemen <video> + <canvas>.
    """

    try:
        frame = decode_base64_image(payload.image)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    recognizer = request.app.state.recognition
    anti_spoof = request.app.state.anti_spoof
    last_scan = request.app.state.attendance_last_scan  # dict: nama -> timestamp

    hasil = recognizer.recognize(frame)
    faces = hasil["faces"]

    attendance = AttendanceService()
    results: list[FaceResult] = []

    try:
        for wajah in faces:
            siswa = wajah["siswa"]
            similarity = wajah["similarity"]
            confidence = wajah["confidence"]
            bbox = tuple(int(v) for v in wajah["bbox"])

            is_real, spoof_score = anti_spoof.is_real(frame, wajah["bbox"])

            status = None

            if is_real and siswa is not None:
                nama = siswa.nama.strip()
                sekarang = time.time()

                if nama not in last_scan or sekarang - last_scan[nama] > COOLDOWN_DETIK:
                    status = attendance.process_attendance(siswa)
                    last_scan[nama] = sekarang
                else:
                    status = "COOLDOWN"  # sudah diproses baru-baru ini, tidak insert ulang

            results.append(
                FaceResult(
                    nama=siswa.nama if siswa else None,
                    siswa_id=siswa.id if siswa else None,
                    similarity=similarity,
                    confidence=confidence,
                    is_real=is_real,
                    spoof_score=spoof_score,
                    bbox=bbox,
                    status=status,
                )
            )

        return results

    finally:
        attendance.close()
