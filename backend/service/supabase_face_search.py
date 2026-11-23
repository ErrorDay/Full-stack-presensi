import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from supabase import Client, create_client


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


_client: Optional[Client] = None


def _get_client() -> Client:
    global _client

    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL dan SUPABASE_SERVICE_ROLE_KEY atau "
                "SUPABASE_ANON_KEY belum dikonfigurasi"
            )

        _client = create_client(url, key)

    return _client


def cari_siswa_terdekat(
    embedding: list,
    top_k: int = 1,
    threshold: float = 0.4,
) -> Optional[dict]:
    """
    Cari embedding terdekat melalui RPC Supabase/pgvector.

    distance lebih kecil berarti lebih mirip. Jika jarak cosine melebihi
    threshold, wajah dianggap tidak dikenal.
    """
    if len(embedding) != 512:
        raise ValueError("Embedding harus memiliki tepat 512 dimensi")
    if top_k < 1:
        raise ValueError("top_k harus minimal 1")
    if threshold < 0 or threshold > 2:
        raise ValueError("threshold cosine harus berada pada rentang 0 sampai 2")

    vector_text = "[" + ",".join(format(float(value), ".9g") for value in embedding) + "]"

    response = (
        _get_client()
        .rpc(
            "cari_siswa_terdekat",
            {
                "query_embedding": vector_text,
                "match_threshold": threshold,
                "match_count": top_k,
            },
        )
        .execute()
    )

    rows = response.data or []
    if not rows:
        return None

    return rows[0]
