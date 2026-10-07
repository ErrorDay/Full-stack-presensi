from pathlib import Path

from anti_spoof.onnx_inference import AntiSpoofingONNX

BASE_DIR = Path(__file__).resolve().parent.parent

class AntiSpoofService:

    def __init__(self):

        model_path = (
            Path(__file__).resolve().parent.parent
            / "anti_spoof"
            / "weights"
            / "MiniFASNetV2.onnx"  # FIX: sebelumnya "MiniFASNetv2.onnx" (v kecil),
                                     # tidak cocok dengan nama file asli di disk.
        )

        self.model = AntiSpoofingONNX(
            model_path=str(model_path)
        )

    def is_real(
        self,
        frame,
        bbox
    ):
        """
        bbox = (x1,y1,x2,y2)

        Return:
            (True, score)
            (False, score)
        """

        result = self.model.predict(
            frame,
            bbox
        )

        return (
            result["label"] == "Real",
            result["score"]
        )
