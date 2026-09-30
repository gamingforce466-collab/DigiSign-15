import binascii
import base64
import json
import zlib
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

import qrcode
import cv2
import numpy as np


def _encode_payload(metadata):
    verify_url = metadata.get("verify_url")
    if not verify_url:
        return json.dumps(metadata, separators=(",", ":"), sort_keys=True)

    parts = urlsplit(verify_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["doc_id"] = str(metadata["doc_id"])
    serialized = json.dumps(
        {key: value for key, value in metadata.items() if key != "verify_url"},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    query["m"] = base64.urlsafe_b64encode(zlib.compress(serialized, 9)).decode("ascii").rstrip("=")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def decode_verification_query(query):
    encoded = query.get("m", "")
    if isinstance(encoded, (list, tuple)):
        encoded = encoded[0] if encoded else ""
    if encoded:
        try:
            token = str(encoded)
            compressed = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
            decompressor = zlib.decompressobj()
            serialized = decompressor.decompress(compressed, 4096)
            if decompressor.unconsumed_tail or decompressor.unused_data or not decompressor.eof:
                return None
            metadata = json.loads(serialized)
        except (binascii.Error, UnicodeDecodeError, ValueError, zlib.error):
            return None
        doc_id = query.get("doc_id", "")
        if isinstance(doc_id, (list, tuple)):
            doc_id = doc_id[0] if doc_id else ""
        if not isinstance(metadata, dict) or metadata.get("doc_id") != doc_id:
            return None
        return metadata

    metadata = {}
    for key, value in query.items():
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        metadata[key] = value
    return metadata if metadata.get("doc_id") else None


def decode_verification_url(url):
    query = parse_qs(urlsplit(url).query, keep_blank_values=True)
    metadata = decode_verification_query(query)
    if metadata is not None:
        metadata["verify_url"] = url
    return metadata


def _decode_payload(data):
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError:
        parts = urlsplit(data)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            return None
        parsed = decode_verification_url(data)
    return parsed if isinstance(parsed, dict) else None


def generate_qr_image(metadata):
    payload = _encode_payload(metadata)
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=6, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return img


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


def decode_qr_image(pil_image):
    rgb = pil_image.convert("RGB")
    arr = np.array(rgb)
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    padded = cv2.copyMakeBorder(bgr, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    for factory in _detector_factories():
        for candidate in (bgr, padded):
            try:
                data, _, _ = factory().detectAndDecode(candidate)
            except cv2.error:
                continue
            if not data:
                continue
            parsed = _decode_payload(data)
            if parsed is not None:
                return parsed
    return None


def decode_qr_image_multiple(pil_image):
    rgb = pil_image.convert("RGB")
    arr = np.array(rgb)
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    padded = cv2.copyMakeBorder(bgr, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    results = []
    seen = set()
    for factory in _detector_factories():
        detector = factory()
        for candidate in (bgr, padded):
            try:
                found, values, _, _ = detector.detectAndDecodeMulti(candidate)
            except (cv2.error, AttributeError):
                continue
            if not found:
                continue
            for value in values:
                if not value or value in seen:
                    continue
                parsed = _decode_payload(value)
                if parsed is not None:
                    results.append(parsed)
                    seen.add(value)
    if results:
        return results
    decoded = decode_qr_image(pil_image)
    return [decoded] if decoded is not None else []


def decode_qr_from_images(pil_images):
    results = []
    for img in pil_images:
        decoded = decode_qr_image(img)
        if decoded is not None:
            results.append(decoded)
    return results
