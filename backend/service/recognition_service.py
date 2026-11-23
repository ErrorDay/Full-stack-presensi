# recognition_service.py — bagian atas, versi bersih
import time

import numpy as np
from insightface.app import FaceAnalysis

from database.models import Siswa
from database.session import SessionLocal
from service.supabase_face_search import cari_siswa_terdekat


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

    def reload_embeddings(self):
        """Tidak diperlukan lagi: pencarian dibaca langsung dari Supabase."""
        return

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

            match = cari_siswa_terdekat(
                embedding.tolist(),
                top_k=1,
                threshold=1.0 - self.threshold,
            )

            best_score = -1.0
            best_match = None

            if match is not None:
                db = SessionLocal()
                try:
                    siswa = (
                        db.query(Siswa)
                        .filter(
                            Siswa.id == int(match["siswa_id"]),
                            Siswa.status == "AKTIF",
                        )
                        .first()
                    )
                finally:
                    db.close()

                if siswa is not None:
                    best_match = siswa
                    best_score = float(
                        1.0 - float(match["cosine_distance"])
                    )

            x1, y1, x2, y2 = map(
                int,
                face.bbox
            )

            confidence = round(
                max(best_score, 0.0) * 100,
                2
            )

            print(
                f"{best_match.nama if best_match else 'Unknown'} "
                f"| similarity = {best_score:.4f}"
            )

            if (
                best_match is not None
                and best_score >= self.threshold
            ):

                results.append(
                    {
                        "siswa": best_match,
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
