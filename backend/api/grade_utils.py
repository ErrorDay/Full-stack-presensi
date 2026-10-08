"""Conversion helpers between Supabase numeric grades and Roman labels."""

ROMAN_TO_INT = {"X": 10, "XI": 11, "XII": 12}
INT_TO_ROMAN = {grade: roman for roman, grade in ROMAN_TO_INT.items()}


def tingkat_ke_grade(grade: int | str | None) -> int | str:
    """Normalize a numeric or Roman grade to the frontend's numeric grade."""
    if grade is None:
        return ""
    if isinstance(grade, int):
        return grade if grade in INT_TO_ROMAN else str(grade)
    value = grade.strip().upper()
    if value in ROMAN_TO_INT:
        return ROMAN_TO_INT[value]
    try:
        return int(value)
    except ValueError:
        return grade


def grade_ke_tingkat(grade: int | str) -> str:
    """Convert grade 10/11/12 (or X/XI/XII) to its Roman display label."""
    normalized = tingkat_ke_grade(grade)
    if isinstance(normalized, int):
        return INT_TO_ROMAN.get(normalized, str(normalized))
    return str(normalized)
