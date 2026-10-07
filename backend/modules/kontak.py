#Kontak.py
import json
import os

KONTAK_FILE = "kontak.json"


def load_kontak() -> dict:
    if not os.path.exists(KONTAK_FILE):
        return {}
    try:
        with open(KONTAK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] load_kontak: {e}")
        return {}


def simpan_kontak(data: dict) -> bool:
    try:
        with open(KONTAK_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[ERROR] simpan_kontak: {e}")
        return False


def set_kontak_kelas(
    kelas: str,
    walas_email: str = None,
    aswalas_email: str = None,
    walas_wa: str = None,
    aswalas_wa: str = None,
) -> bool:
    """Simpan/update kontak email & WA (opsional) untuk satu kelas."""
    data = load_kontak()
    data[kelas] = {
        "walas_email": walas_email,
        "aswalas_email": aswalas_email,
        "walas_wa": _format_nomor(walas_wa) if walas_wa else None,
        "aswalas_wa": _format_nomor(aswalas_wa) if aswalas_wa else None,
    }
    return simpan_kontak(data)


def get_kontak_kelas(kelas: str) -> dict:
    """Return dict kontak kelas, atau {} jika belum diset."""
    data = load_kontak()
    return data.get(kelas, {})


def _format_nomor(nomor: str) -> str:
    nomor = nomor.strip().replace(" ", "").replace("-", "")
    if nomor.startswith("0"):
        nomor = "62" + nomor[1:]
    elif nomor.startswith("+"):
        nomor = nomor[1:]
    return nomor
