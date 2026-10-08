"""Generate 512-dimensional buffalo_l face vectors for students with photos."""

import os

import cv2
import modules._patch_torch_deps  # noqa: F401
import numpy as np
from insightface.app import FaceAnalysis

from database.models import FaceEmbedding, Siswa
from database.session import SessionLocal

EMBEDDING_DIMENSION = 512
MODEL_NAME = "buffalo_l"


def baca_gambar(path: str) -> np.ndarray | None:
    try:
        data = np.fromfile(path, dtype=np.uint8)
        if data.size == 0:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except OSError as exc:
        print(f"[ERROR] Tidak dapat membaca foto {path!r}: {exc}")
        return None


def generate_embeddings() -> None:
    app = FaceAnalysis(name=MODEL_NAME, providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(960, 960))
    db = SessionLocal()

    total = 0
    gagal = 0
    skip = 0
    path_tidak_ada = 0
    try:
        siswa_list = db.query(Siswa).filter(Siswa.status == "Aktif").all()

        for siswa in siswa_list:
            try:
                old_embedding = (
                    db.query(FaceEmbedding)
                    .filter(FaceEmbedding.student_id == siswa.id)
                    .first()
                )
                if old_embedding:
                    print(f"[SKIP] {siswa.name}: embedding sudah ada")
                    skip += 1
                    continue

                foto = siswa.foto
                if not foto:
                    print(f"[SKIP] {siswa.name}: path foto belum diisi")
                    skip += 1
                    continue
                if not os.path.exists(foto):
                    print(f"[GAGAL] Path foto tidak ditemukan: {foto}")
                    path_tidak_ada += 1
                    gagal += 1
                    continue

                image = baca_gambar(foto)
                if image is None:
                    print(f"[GAGAL] Foto tidak dapat di-decode: {foto}")
                    gagal += 1
                    continue

                faces = app.get(image)
                if not faces:
                    print(f"[GAGAL] Tidak ada wajah terdeteksi: {siswa.name}")
                    gagal += 1
                    continue
                if len(faces) > 1:
                    print(f"[PERINGATAN] Lebih dari satu wajah: {siswa.name}")

                face = max(faces, key=lambda candidate: candidate.det_score)
                embedding = np.asarray(face.embedding, dtype=np.float32)
                if embedding.shape != (EMBEDDING_DIMENSION,) or not np.isfinite(embedding).all():
                    raise ValueError(
                        f"Embedding harus memiliki {EMBEDDING_DIMENSION} nilai finite; "
                        f"shape diperoleh {embedding.shape}"
                    )

                db.add(
                    FaceEmbedding(
                        student_id=siswa.id,
                        embedding=embedding.tolist(),
                        model=MODEL_NAME,
                    )
                )
                db.commit()
                total += 1
                print(f"[OK] {siswa.name}")
            except Exception as exc:
                db.rollback()
                gagal += 1
                print(f"[ERROR] Gagal memproses {siswa.name} ({siswa.id}): {exc}")

        print("\n====================")
        print("GENERATE SELESAI")
        print("====================")
        print(f"Berhasil        : {total}")
        print(f"Skip            : {skip}")
        print(f"Gagal           : {gagal}")
        print(f"  - path hilang : {path_tidak_ada}")
    finally:
        db.close()


if __name__ == "__main__":
    generate_embeddings()
