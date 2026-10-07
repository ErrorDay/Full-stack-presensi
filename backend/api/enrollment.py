"""
api/enrollment.py
Endpoint pendaftaran wajah siswa. Mendukung DUA alur (sesuai keputusan):

1. Upload foto satu file — mirip generate_embeddings.py versi lama,
   tapi jadi endpoint langsung (tidak perlu jalankan script terpisah).
2. Live-camera multi-pose — terinspirasi ambilWajah.js di e-course:
   browser kirim beberapa frame (depan/kiri/kanan), server pilih
   capture dengan skor deteksi (det_score) InsightFace terbaik.

CATATAN PENTING: FaceEmbedding.siswa_id masih unique=True di skema
saat ini, jadi kedua alur ini selalu UPSERT satu baris embedding
final per siswa — bukan menyimpan banyak pose sekaligus. Live-camera
multi-pose di sini hanya membantu MEMILIH capture terbaik dari
beberapa sudut, bukan menyimpan semuanya.
"""

import json
import os
import uuid

import cv2
import numpy as np

# WAJIB diimpor sebelum modul lain yang menyentuh InsightFace.
import modules._patch_torch_deps  # noqa: F401

from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from pydantic import BaseModel

from database.session import SessionLocal
from database.models import Siswa, FaceEmbedding
from api.utils import decode_base64_image

router = APIRouter()

UPLOAD_DIR = "static/uploads/siswa"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class EnrollCameraRequest(BaseModel):
    # Beberapa frame base64 dari live capture, mis. ["depan", "kiri", "kanan"]
    # urutan tidak wajib, cukup kirim semua frame yang berhasil di-capture.
    frames: list[str]


class EnrollResponse(BaseModel):
    siswa_id: int
    nama: str
    foto: str
    pesan: str


def _get_siswa_or_404(db, siswa_id: int) -> Siswa:
    siswa = db.query(Siswa).filter(Siswa.id == siswa_id).first()
    if siswa is None:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
    return siswa


def _simpan_embedding(db, siswa_id: int, embedding: np.ndarray) -> None:
    """
    Upsert FaceEmbedding — karena siswa_id unique, kalau sudah ada
    baris lama, di-replace embedding-nya (bukan bikin baris baru).
    """
    embedding_json = json.dumps(embedding.astype(np.float32).tolist())

    existing = (
        db.query(FaceEmbedding)
        .filter(FaceEmbedding.siswa_id == siswa_id)
        .first()
    )

    if existing:
        existing.embedding = embedding_json
    else:
        db.add(FaceEmbedding(siswa_id=siswa_id, embedding=embedding_json))

    db.commit()


@router.post("/{siswa_id}/enroll/upload", response_model=EnrollResponse)
async def enroll_upload(siswa_id: int, request: Request, file: UploadFile = File(...)):
    """
    Alur 1: upload satu foto wajah.
    Setara dengan generate_embeddings.py lama, tapi langsung per-siswa
    dan tanpa perlu jalankan script terpisah.
    """

    db = SessionLocal()

    try:
        siswa = _get_siswa_or_404(db, siswa_id)

        ext = os.path.splitext(file.filename)[1] or ".jpg"
        filename = f"{siswa_id}_{uuid.uuid4().hex[:8]}{ext}"
        save_path = os.path.join(UPLOAD_DIR, filename)

        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)

        image = cv2.imread(save_path)
        if image is None:
            os.remove(save_path)
            raise HTTPException(status_code=400, detail="File bukan gambar yang valid")

        recognizer = request.app.state.recognition
        faces = recognizer.app.get(image)

        if len(faces) == 0:
            os.remove(save_path)
            raise HTTPException(status_code=400, detail="Tidak ada wajah terdeteksi pada foto")

        # Kalau lebih dari satu wajah, ambil yang skor deteksinya tertinggi
        # (paling jelas/besar), bukan asal wajah pertama.
        face = max(faces, key=lambda f: f.det_score)

        siswa.foto = save_path
        _simpan_embedding(db, siswa.id, face.embedding)
        db.commit()

        # Reload cache di RecognitionService supaya siswa baru langsung
        # bisa dikenali tanpa restart server — sama seperti komentar
        # asli "digunakan ketika ada siswa baru" di recognition_service.py.
        recognizer.reload_embeddings()

        return EnrollResponse(
            siswa_id=siswa.id,
            nama=siswa.nama,
            foto=save_path,
            pesan="Enrollment berhasil dari foto upload",
        )

    finally:
        db.close()


@router.post("/{siswa_id}/enroll/camera", response_model=EnrollResponse)
def enroll_camera(siswa_id: int, payload: EnrollCameraRequest, request: Request):
    """
    Alur 2: live-camera multi-pose (depan/kiri/kanan), terinspirasi
    ambilWajah.js di e-course. Server memilih frame dengan det_score
    InsightFace tertinggi sebagai capture final.
    """

    if not payload.frames:
        raise HTTPException(status_code=400, detail="Tidak ada frame yang dikirim")

    db = SessionLocal()

    try:
        siswa = _get_siswa_or_404(db, siswa_id)
        recognizer = request.app.state.recognition

        best_face = None
        best_frame = None

        for frame_b64 in payload.frames:
            try:
                frame = decode_base64_image(frame_b64)
            except ValueError:
                continue  # skip frame yang gagal didecode, jangan gagalkan semua

            faces = recognizer.app.get(frame)
            if len(faces) == 0:
                continue

            face = max(faces, key=lambda f: f.det_score)

            if best_face is None or face.det_score > best_face.det_score:
                best_face = face
                best_frame = frame

        if best_face is None:
            raise HTTPException(
                status_code=400,
                detail="Tidak ada wajah terdeteksi di semua frame yang dikirim",
            )

        ext = ".jpg"
        filename = f"{siswa_id}_{uuid.uuid4().hex[:8]}{ext}"
        save_path = os.path.join(UPLOAD_DIR, filename)
        cv2.imwrite(save_path, best_frame)

        siswa.foto = save_path
        _simpan_embedding(db, siswa.id, best_face.embedding)
        db.commit()

        recognizer.reload_embeddings()

        return EnrollResponse(
            siswa_id=siswa.id,
            nama=siswa.nama,
            foto=save_path,
            pesan=f"Enrollment berhasil, dipilih dari {len(payload.frames)} frame (det_score={best_face.det_score:.3f})",
        )

    finally:
        db.close()
