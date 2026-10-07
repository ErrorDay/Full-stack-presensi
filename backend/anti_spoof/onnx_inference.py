import cv2
import numpy as np
import onnxruntime as ort


class AntiSpoofingONNX:
    """
    MiniFASNetV2 ONNX Runtime
    """

    def __init__(
        self,
        model_path: str,
        scale: float = 2.7,
        providers: list[str] | None = None
    ) -> None:

        if providers is None:
            providers = [
                "CPUExecutionProvider"
            ]

        self.session = ort.InferenceSession(
            model_path,
            providers=providers
        )

        self.scale = scale

        input_info = self.session.get_inputs()[0]

        self.input_name = input_info.name
        self.input_size = tuple(input_info.shape[2:])

        output_info = self.session.get_outputs()[0]

        self.output_name = output_info.name

    def _xyxy2xywh(
        self,
        bbox: tuple[int, int, int, int]
    ) -> list[int]:
        """
        Convert

        (x1,y1,x2,y2)

        menjadi

        (x,y,w,h)
        """

        x1, y1, x2, y2 = bbox

        return [
            int(x1),
            int(y1),
            int(x2 - x1),
            int(y2 - y1)
        ]

    def _crop_face(
        self,
        image: np.ndarray,
        bbox: list[int]
    ) -> np.ndarray | None:
        """
        Crop wajah sesuai bbox.
        """

        image_height, image_width = image.shape[:2]

        x, y, width, height = bbox

        if width <= 0 or height <= 0:
            return None

        scale = min(
            (image_height - 1) / height,
            (image_width - 1) / width,
            self.scale
        )

        crop_width = width * scale
        crop_height = height * scale

        center_x = x + width / 2
        center_y = y + height / 2

        x1 = max(
            0,
            int(center_x - crop_width / 2)
        )

        y1 = max(
            0,
            int(center_y - crop_height / 2)
        )

        x2 = min(
            image_width - 1,
            int(center_x + crop_width / 2)
        )

        y2 = min(
            image_height - 1,
            int(center_y + crop_height / 2)
        )

        face = image[
            y1:y2 + 1,
            x1:x2 + 1
        ]

        if face.size == 0:
            return None

        return cv2.resize(
            face,
            self.input_size[::-1]
        )

    def _preprocess(
        self,
        image: np.ndarray,
        bbox: list[int]
    ) -> np.ndarray | None:
        """
        Preprocessing sebelum inference.
        """

        face = self._crop_face(
            image,
            bbox
        )

        if face is None:
            return None

        face = face.astype(
            np.float32
        )

        face = np.transpose(
            face,
            (2, 0, 1)
        )

        face = np.expand_dims(
            face,
            axis=0
        )

        return face

    @staticmethod
    def _softmax(
        logits: np.ndarray
    ) -> np.ndarray:
        """
        Softmax.
        """

        logits = logits - np.max(
            logits,
            axis=1,
            keepdims=True
        )

        exp = np.exp(logits)

        return exp / (
            np.sum(
                exp,
                axis=1,
                keepdims=True
            ) + 1e-8
        )

    def predict(
        self,
        frame: np.ndarray,
        bbox_xyxy: tuple[int, int, int, int]
    ) -> dict:
        """
        Prediksi Real / Fake.

        bbox berasal dari InsightFace.
        """

        bbox_xywh = self._xyxy2xywh(
            bbox_xyxy
        )

        input_tensor = self._preprocess(
            frame,
            bbox_xywh
        )

        if input_tensor is None:

            return {
                "is_real": False,
                "label": "Invalid",
                "score": 0.0
            }

        output = self.session.run(
            [self.output_name],
            {
                self.input_name:
                input_tensor
            }
        )[0]

        probability = self._softmax(
            output
        )

        label = int(
            np.argmax(probability)
        )

        score = float(
            probability[0][label]
        )

        return {
            "is_real": label == 1,
            "label": (
                "Real"
                if label == 1
                else "Fake"
            ),
            "score": score
        }
