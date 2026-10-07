"""
api/utils.py
Helper bersama untuk endpoint API (decode frame base64 dari browser).
"""

import base64
import numpy as np
import cv2


def decode_base64_image(base64_str: str) -> np.ndarray:
    """
    Terima string base64 (boleh dengan prefix "data:image/jpeg;base64,"
    atau tanpa prefix), kembalikan frame BGR (numpy array) siap dipakai
    RecognitionService / AntiSpoofService — format yang sama seperti
    frame dari cv2.VideoCapture() di tes_kamera.py.
    """

    if "," in base64_str:
        # buang prefix "data:image/jpeg;base64,"
        base64_str = base64_str.split(",", 1)[1]

    img_bytes = base64.b64decode(base64_str)
    img_array = np.frombuffer(img_bytes, dtype=np.uint8)

    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    if frame is None:
        raise ValueError("Gagal decode gambar — data base64 tidak valid.")

    return frame
