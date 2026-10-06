"""
api/grade_utils.py
Konversi antara "tingkat" Romawi yang tersimpan di database
(Kelas.tingkat = "X"/"XI"/"XII", konsisten dengan nama folder
dataset/ untuk foto) dan angka (10/11/12) yang dipakai frontend
React (GRADES = [10, 11, 12] di Kelas.jsx, perbandingan pakai ===
jadi tipe datanya harus persis integer).
"""

ROMAN_TO_INT = {"X": 10, "XI": 11, "XII": 12}
INT_TO_ROMAN = {10: "X", 11: "XI", 12: "XII"}


def tingkat_ke_grade(tingkat: str) -> int | str:
    """Kelas.tingkat (database) -> grade (dikirim ke frontend)."""
    if tingkat is None:
        return ""
    key = tingkat.strip().upper()
    if key in ROMAN_TO_INT:
        return ROMAN_TO_INT[key]
    try:
        return int(tingkat)
    except (TypeError, ValueError):
        # Nilai tingkat tidak dikenali (bukan X/XI/XII maupun angka) --
        # dikembalikan apa adanya supaya tidak crash, tapi TIDAK akan
        # cocok dengan GRADES=[10,11,12] di frontend (tidak akan
        # muncul di grouping manapun). Perlu dirapikan manual di data.
        return tingkat


def grade_ke_tingkat(grade) -> str:
    """grade (dari frontend, bisa int atau str) -> Kelas.tingkat (database)."""
    try:
        angka = int(grade)
        return INT_TO_ROMAN.get(angka, str(grade))
    except (TypeError, ValueError):
        return str(grade)
