"""Face recognition using InsightFace buffalo_l embeddings."""

import time

import numpy as np
from insightface.app import FaceAnalysis

from database.models import FaceEmbedding, Siswa
from database.session import SessionLocal

EMBEDDING_DIMENSION = 512
MODEL_NAME = "buffalo_l"


class RecognitionService:
    def __init__(
        self,
        threshold: float = 0.70,
        providers: list[str] | None = None,
    ):
        self.threshold = threshold
        self.app = FaceAnalysis(
            name=MODEL_NAME,
            providers=providers or ["CPUExecutionProvider"],
        )
        self.app.prepare(ctx_id=0, det_size=(640, 640))
        self.known_faces: list[dict] = []
        self.load_embeddings()

    def load_embeddings(self) -> None:
        """Load and normalize all active-student vectors into memory."""
        db = SessionLocal()
        try:
            rows = (
                db.query(FaceEmbedding, Siswa)
                .join(Siswa, FaceEmbedding.student_id == Siswa.id)
                .filter(Siswa.status == "Aktif")
                .all()
            )
            loaded: list[dict] = []
            for face_embedding, siswa in rows:
                embedding = np.asarray(face_embedding.embedding, dtype=np.float32)
                if embedding.shape != (EMBEDDING_DIMENSION,):
                    raise ValueError(
                        f"Embedding {face_embedding.id} untuk siswa {siswa.id} "
                        f"harus berdimensi {EMBEDDING_DIMENSION}, "
                        f"mendapatkan shape {embedding.shape}."
                    )

                norm = float(np.linalg.norm(embedding))
                if not np.isfinite(norm) or norm == 0:
                    raise ValueError(
                        f"Embedding {face_embedding.id} untuk siswa {siswa.id} "
                        "bernilai tidak valid atau memiliki norm nol."
                    )

                loaded.append(
                    {"siswa": siswa, "embedding": embedding / norm}
                )

            self.known_faces = loaded
            print(f"[INFO] {len(self.known_faces)} embeddings dimuat.")
        finally:
            db.close()

    def reload_embeddings(self) -> None:
        self.load_embeddings()

    @staticmethod
    def cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        return float(np.dot(emb1, emb2))

    def recognize(self, frame) -> dict:
        start = time.perf_counter()
        results = []

        for face in self.app.get(frame):
            embedding = np.asarray(face.embedding, dtype=np.float32)
            if embedding.shape != (EMBEDDING_DIMENSION,):
                raise ValueError(
                    f"{MODEL_NAME} menghasilkan embedding dengan shape "
                    f"{embedding.shape}; diharapkan ({EMBEDDING_DIMENSION},)."
                )

            norm = float(np.linalg.norm(embedding))
            if not np.isfinite(norm) or norm == 0:
                raise ValueError(f"{MODEL_NAME} menghasilkan embedding tidak valid.")
            embedding = embedding / norm

            best_score = -1.0
            best_match = None
            for known in self.known_faces:
                score = self.cosine_similarity(embedding, known["embedding"])
                if score > best_score:
                    best_score = score
                    best_match = known

            x1, y1, x2, y2 = map(int, face.bbox)
            confidence = round(max(best_score, 0.0) * 100, 2)
            print(
                f"{best_match['siswa'].name if best_match else 'Unknown'} "
                f"| similarity = {best_score:.4f}"
            )

            siswa = (
                best_match["siswa"]
                if best_match is not None and best_score >= self.threshold
                else None
            )
            results.append(
                {
                    "siswa": siswa,
                    "similarity": float(best_score),
                    "confidence": confidence,
                    "bbox": (x1, y1, x2, y2),
                    "embedding": embedding,
                    "face": face,
                }
            )

        results.sort(key=lambda item: item["similarity"], reverse=True)
        return {"faces": results, "elapsed": time.perf_counter() - start}
