# modules/_patch_torch_deps.py
"""
Stub albumentations.pytorch dan insightface.app.mask_renderer,
karena keduanya menarik torch (bermasalah di environment ini)
dan kita tidak memakai fitur yang membutuhkan torch sama sekali.
HARUS diimpor paling pertama, sebelum modul lain apapun.
"""
import sys
import types

_dummy_torch_pytorch = types.ModuleType("albumentations.pytorch")
_dummy_torch_pytorch.ToTensorV2 = object
sys.modules["albumentations.pytorch"] = _dummy_torch_pytorch

sys.modules["insightface.app.mask_renderer"] = types.ModuleType(
    "insightface.app.mask_renderer"
)
