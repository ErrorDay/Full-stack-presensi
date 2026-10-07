import json
import os

import cv2
import numpy as np

from insightface.app import FaceAnalysis

from database.session import SessionLocal
from database.models import (
    Siswa,
    FaceEmbedding
)


app = FaceAnalysis(
    providers=['CPUExecutionProvider']
)

app.prepare(
    ctx_id=0,
    det_size=(960, 960)
)


def baca_gambar(path: str):
    """
    Pengganti cv2.imread(path) langsung.

    cv2.imread() punya bug lama di Windows: gagal decode file yang
    pathnya mengandung spasi, tanda kurung, atau karakter non-ASCII
    -- walaupun filenya benar-benar ada -- dan cuma melempar pesan
    generik "can't open/read file: check file path/integrity".

    np.fromfile() (baca byte mentah, aman untuk path apapun) +
    cv2.imdecode() (decode dari byte, bukan dari path) tidak
    kena masalah ini sama sekali.
    """
    try:
        data = np.fromfile(path, dtype=np.uint8)
        if data.size == 0:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def generate_embeddings():
    db = SessionLocal()

    siswa_list = db.query(Siswa).all()

    total = 0
    gagal = 0
    skip = 0
    path_tidak_ada = 0

    for siswa in siswa_list:
        try:
            # ==========================
            # Cek apakah embedding sudah ada
            # ==========================
            old_embedding = (
                db.query(FaceEmbedding)
                .filter(
                    FaceEmbedding.siswa_id == siswa.id
                )
                .first()
            )

            if old_embedding:
                print(f"[SKIP] {siswa.nama}")
                skip += 1
                continue

            foto = siswa.foto

            if not foto:
                print(
                    f"[GAGAL] Path foto kosong: {siswa.nama}"
                )
                gagal += 1
                continue

            # Cek dulu apakah filenya benar-benar ada di disk --
            # supaya ketahuan pasti mana yang "file memang hilang"
            # vs "file ada tapi cv2 gagal decode" (dua akar masalah
            # yang beda, butuh penanganan beda).
            if not os.path.exists(foto):
                print(
                    f"[GAGAL] Path tidak ditemukan di disk: {foto}"
                )
                path_tidak_ada += 1
                gagal += 1
                continue

            image = baca_gambar(foto)

            if image is None:
                print(
                    f"[GAGAL] File ada tapi gagal di-decode (rusak/format tidak didukung): {foto}"
                )
                gagal += 1
                continue

            faces = app.get(image)

            if len(faces) == 0:
                print(
                    f"[GAGAL] Tidak ada wajah: {siswa.nama}"
                )
                gagal += 1
                continue

            if len(faces) > 1:
                print(
                    f"[PERINGATAN] Lebih dari satu wajah: {siswa.nama}"
                )

            face = faces[0]

            embedding = (
                face.embedding.astype(np.float32)
            )

            embedding_json = json.dumps(
                embedding.tolist()
            )

            new_embedding = FaceEmbedding(
                siswa_id=siswa.id,
                embedding=embedding_json
            )

            db.add(new_embedding)
            db.commit()

            total += 1

            print(
                f"[OK] {siswa.nama}"
            )

        except Exception as e:
            db.rollback()

            gagal += 1

            print(
                f"[ERROR] {siswa.nama}"
            )
            print(e)

    print("\n====================")
    print("GENERATE SELESAI")
    print("====================")
    print(f"Berhasil        : {total}")
    print(f"Skip            : {skip}")
    print(f"Gagal           : {gagal}")
    print(f"  - path hilang : {path_tidak_ada}")

    db.close()


if __name__ == "__main__":
    generate_embeddings()
