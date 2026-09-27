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


def decode_qr_image(pil_image):
    rgb = pil_image.convert("RGB")
    arr = np.array(rgb)
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(bgr)
    if not data:
        return None
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return None


def decode_qr_from_images(pil_images):
    results = []
    for img in pil_images:
        decoded = decode_qr_image(img)
        if decoded is not None:
            results.append(decoded)
    return results
