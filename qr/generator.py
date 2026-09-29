import json
import qrcode
import cv2
import numpy as np


def generate_qr_image(metadata):
    payload = json.dumps(metadata, separators=(",", ":"), sort_keys=True)
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=6, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return img


<<<<<<< HEAD
def _detector_factories():
    """Detektor QR OpenCV, berurutan dari yang paling andal.

    QRCodeDetectorAruco (OpenCV >= 4.8) membaca QR berisi metadata panjang secara konsisten,
    sedangkan QRCodeDetector bawaan gagal pada sekitar separuh QR sebesar itu. Detektor bawaan
    tetap dipakai sebagai cadangan.
    """
    factories = []
    aruco = getattr(cv2, "QRCodeDetectorAruco", None)
    if aruco is not None:
        factories.append(aruco)
    factories.append(cv2.QRCodeDetector)
    return factories


=======
>>>>>>> e5f9e3f2d4901c926d7e0edf40d3f99ca6aad194
def decode_qr_image(pil_image):
    rgb = pil_image.convert("RGB")
    arr = np.array(rgb)
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
<<<<<<< HEAD
    padded = cv2.copyMakeBorder(bgr, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    for factory in _detector_factories():
        for candidate in (bgr, padded):
            try:
                data, _, _ = factory().detectAndDecode(candidate)
            except cv2.error:
                continue
            if not data:
                continue
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    return None
=======
    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(bgr)
    if not data:
        return None
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return None
>>>>>>> e5f9e3f2d4901c926d7e0edf40d3f99ca6aad194


def decode_qr_from_images(pil_images):
    results = []
    for img in pil_images:
        decoded = decode_qr_image(img)
        if decoded is not None:
            results.append(decoded)
    return results
