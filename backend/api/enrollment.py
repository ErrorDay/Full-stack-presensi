"""Face enrollment endpoints for uploaded images and live camera frames."""

import os
import uuid

import cv2
import numpy as np
import modules._patch_torch_deps  # noqa: F401
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from api.utils import decode_base64_image
from database.models import FaceEmbedding, Siswa
from database.session import SessionLocal

router = APIRouter()

EMBEDDING_DIMENSION = 512
MODEL_NAME = "buffalo_l"
UPLOAD_DIR = "static/uploads/siswa"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class EnrollCameraRequest(BaseModel):
    frames: list[str]


class EnrollResponse(BaseModel):
    student_id: uuid.UUID
    name: str
    foto: str
    pesan: str


def _get_siswa_or_404(db, student_id: uuid.UUID) -> Siswa:
    siswa = db.query(Siswa).filter(Siswa.id == student_id).first()
    if siswa is None:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
    return siswa


def _store_embedding(db, student_id: uuid.UUID, embedding: np.ndarray) -> None:
    vector = np.asarray(embedding, dtype=np.float32)
    if vector.shape != (EMBEDDING_DIMENSION,) or not np.isfinite(vector).all():
        raise HTTPException(
            status_code=422,
            detail=(
                f"Embedding {MODEL_NAME} harus berupa vektor valid "
                f"{EMBEDDING_DIMENSION} dimensi."
            ),
        )

    existing = (
        db.query(FaceEmbedding)
        .filter(FaceEmbedding.student_id == student_id)
        .first()
    )
    if existing:
        existing.embedding = vector.tolist()
        existing.model = MODEL_NAME
    else:
        db.add(
            FaceEmbedding(
                id=uuid.uuid4(),
                student_id=student_id,
                embedding=vector.tolist(),
                model=MODEL_NAME,
            )
        )


def _reload_recognition(request: Request) -> None:
    try:
        request.app.state.recognition.reload_embeddings()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Embedding tersimpan, tetapi cache recognition gagal dimuat: {exc}",
        ) from exc


@router.post("/{student_id}/enroll/upload", response_model=EnrollResponse)
async def enroll_upload(
    student_id: uuid.UUID, request: Request, file: UploadFile = File(...)
):
    db = SessionLocal()
    save_path: str | None = None
    committed = False
    try:
        siswa = _get_siswa_or_404(db, student_id)
        content = await file.read()
        image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise HTTPException(
                status_code=400, detail="File bukan gambar yang valid"
            )

        faces = request.app.state.recognition.app.get(image)
        if not faces:
            raise HTTPException(
                status_code=400,
                detail="Tidak ada wajah terdeteksi pada foto",
            )

        face = max(faces, key=lambda candidate: candidate.det_score)
        embedding = np.asarray(face.embedding, dtype=np.float32)
        if embedding.shape != (EMBEDDING_DIMENSION,):
            raise HTTPException(
                status_code=422,
                detail=f"InsightFace menghasilkan embedding bukan {EMBEDDING_DIMENSION} dimensi",
            )

        ext = os.path.splitext(file.filename or "")[1].lower() or ".jpg"
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            ext = ".jpg"
        filename = f"{student_id}_{uuid.uuid4().hex[:8]}{ext}"
        save_path = os.path.join(UPLOAD_DIR, filename)
        if not cv2.imwrite(save_path, image):
            raise HTTPException(
                status_code=500, detail="Gagal menyimpan foto enrollment"
            )

        siswa.foto = save_path
        _store_embedding(db, siswa.id, embedding)
        db.commit()
        committed = True
        _reload_recognition(request)

        return EnrollResponse(
            student_id=siswa.id,
            name=siswa.name,
            foto=save_path,
            pesan="Enrollment berhasil dari foto upload",
        )
    except HTTPException:
        db.rollback()
        if save_path and os.path.exists(save_path) and not committed:
            os.remove(save_path)
        raise
    except Exception as exc:
        db.rollback()
        if save_path and os.path.exists(save_path) and not committed:
            os.remove(save_path)
        raise HTTPException(
            status_code=500, detail=f"Gagal menyimpan enrollment: {exc}"
        ) from exc
    finally:
        db.close()


@router.post("/{student_id}/enroll/camera", response_model=EnrollResponse)
def enroll_camera(
    student_id: uuid.UUID, payload: EnrollCameraRequest, request: Request
):
    if not payload.frames:
        raise HTTPException(status_code=400, detail="Tidak ada frame yang dikirim")

    db = SessionLocal()
    save_path: str | None = None
    committed = False
    try:
        siswa = _get_siswa_or_404(db, student_id)
        recognizer = request.app.state.recognition
        best_face = None
        best_frame = None
        decode_errors = 0

        for frame_b64 in payload.frames:
            try:
                frame = decode_base64_image(frame_b64)
            except ValueError:
                decode_errors += 1
                continue

            faces = recognizer.app.get(frame)
            if not faces:
                continue
            candidate = max(faces, key=lambda item: item.det_score)
            if best_face is None or candidate.det_score > best_face.det_score:
                best_face = candidate
                best_frame = frame

        if best_face is None or best_frame is None:
            detail = (
                "Semua frame gagal didekode"
                if decode_errors == len(payload.frames)
                else "Tidak ada wajah terdeteksi di semua frame yang dikirim"
            )
            raise HTTPException(status_code=400, detail=detail)

        embedding = np.asarray(best_face.embedding, dtype=np.float32)
        if embedding.shape != (EMBEDDING_DIMENSION,):
            raise HTTPException(
                status_code=422,
                detail=f"InsightFace menghasilkan embedding bukan {EMBEDDING_DIMENSION} dimensi",
            )

        filename = f"{student_id}_{uuid.uuid4().hex[:8]}.jpg"
        save_path = os.path.join(UPLOAD_DIR, filename)
        if not cv2.imwrite(save_path, best_frame):
            raise HTTPException(
                status_code=500, detail="Gagal menyimpan foto enrollment"
            )

        siswa.foto = save_path
        _store_embedding(db, siswa.id, embedding)
        db.commit()
        committed = True
        _reload_recognition(request)

        return EnrollResponse(
            student_id=siswa.id,
            name=siswa.name,
            foto=save_path,
            pesan=(
                f"Enrollment berhasil dari {len(payload.frames)} frame "
                f"(det_score={best_face.det_score:.3f})"
            ),
        )
    except HTTPException:
        db.rollback()
        if save_path and os.path.exists(save_path) and not committed:
            os.remove(save_path)
        raise
    except Exception as exc:
        db.rollback()
        if save_path and os.path.exists(save_path) and not committed:
            os.remove(save_path)
        raise HTTPException(
            status_code=500, detail=f"Gagal menyimpan enrollment: {exc}"
        ) from exc
    finally:
        db.close()
