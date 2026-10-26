# recognition_service.py — bagian atas, versi bersih
import json
import time

import numpy as np
from insightface.app import FaceAnalysis

from database.models import FaceEmbedding, Siswa
from database.session import SessionLocal


class RecognitionService:

    def __init__(
        self,
        threshold=0.70,
        providers=["CPUExecutionProvider"]
    ):

        self.threshold = threshold

        self.app = FaceAnalysis(
            providers=providers
        )

        self.app.prepare(
            ctx_id=0,
            det_size=(640, 640)
        )

        self.known_faces = []

        self.load_embeddings()

    def load_embeddings(self):
        """
        Memuat seluruh embedding dari database
        ke dalam RAM agar recognition menjadi cepat.
        """

        db = SessionLocal()

        try:

            self.known_faces.clear()

            data = (
                db.query(
                    FaceEmbedding,
                    Siswa
                )
                .join(
                    Siswa,
                    FaceEmbedding.siswa_id == Siswa.id
                )
                .filter(Siswa.status == "AKTIF")
                # ^ siswa nonaktif (mis. sudah lulus) TETAP punya baris
                # FaceEmbedding di database (tidak dihapus), tapi TIDAK
                # ikut dimuat ke memori -- jadi tidak akan pernah lagi
                # cocok/terdeteksi saat scan kamera.
                .all()
            )

            for embedding_db, siswa in data:

                embedding = np.array(
                    json.loads(
                        embedding_db.embedding
                    ),
                    dtype=np.float32
                )

                # Normalisasi embedding
                embedding /= np.linalg.norm(
                    embedding
                )

                self.known_faces.append(
                    {
                        "siswa": siswa,
                        "embedding": embedding
                    }
                )

            print(
                f"[INFO] {len(self.known_faces)} embeddings dimuat."
            )

        finally:

            db.close()

    def reload_embeddings(self):
        """
        Digunakan ketika ada siswa baru.
        """

        self.load_embeddings()

    @staticmethod
    def cosine_similarity(
        emb1,
        emb2
    ):
        """
        Karena embedding sudah dinormalisasi,
        cosine similarity cukup menggunakan dot product.
        """

        return np.dot(
            emb1,
            emb2
        )

    def recognize(
        self,
        frame
    ):
        """
        Return:

        {
            "faces":[
                {
                    "siswa": objek_siswa / None,
                    "similarity": float,
                    "confidence": float,
                    "bbox": (x1,y1,x2,y2),
                    "embedding": np.ndarray,
                    "face": InsightFaceFace
                }
            ],

            "elapsed": float
        }
        """

        start = time.perf_counter()

        results = []

        faces = self.app.get(frame)

        for face in faces:

            embedding = face.embedding.astype(
                np.float32
            )

            embedding /= np.linalg.norm(
                embedding
            )

            best_score = -1.0
            best_match = None

            for known in self.known_faces:

                score = self.cosine_similarity(
                    embedding,
                    known["embedding"]
                )

                if score > best_score:

                    best_score = score
                    best_match = known

            x1, y1, x2, y2 = map(
                int,
                face.bbox
            )

            confidence = round(
                max(best_score, 0.0) * 100,
                2
            )

            print(
                f"{best_match['siswa'].nama if best_match else 'Unknown'} "
                f"| similarity = {best_score:.4f}"
            )

            if (
                best_match is not None
                and best_score >= self.threshold
            ):

                results.append(
                    {
                        "siswa": best_match["siswa"],
                        "similarity": float(best_score),
                        "confidence": confidence,
                        "bbox": (
                            x1,
                            y1,
                            x2,
                            y2
                        ),
                        "embedding": embedding,
                        "face": face
                    }
                )

            else:

                results.append(
                    {
                        "siswa": None,
                        "similarity": float(best_score),
                        "confidence": confidence,
                        "bbox": (
                            x1,
                            y1,
                            x2,
                            y2
                        ),
                        "embedding": embedding,
                        "face": face
                    }
                )

        results.sort(
            key=lambda x: x["similarity"],
            reverse=True
        )

        elapsed = (
            time.perf_counter() - start
        )

        return {
            "faces": results,
            "elapsed": elapsed
        }
