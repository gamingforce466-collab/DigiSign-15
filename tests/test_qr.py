import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PIL import Image
from qr import generator as qr_module


def test_qr_generate_and_decode_roundtrip():
    metadata = {
        "doc_id": "abc123",
        "name": "Budi Santoso",
        "position": "Ketua Panitia",
        "institution": "Universitas Contoh",
        "date": "2026-09-27",
        "hash": "a" * 64
    }
    image = qr_module.generate_qr_image(metadata)
    decoded = qr_module.decode_qr_image(image)
    assert decoded is not None
    assert decoded["doc_id"] == metadata["doc_id"]
    assert decoded["hash"] == metadata["hash"]


def test_qr_verification_url_opens_page_and_preserves_metadata():
    metadata = {
        "doc_id": "abc123",
        "signer_id": "signer01",
        "name": "Budi Santoso",
        "position": "Ketua Panitia",
        "institution": "Universitas Contoh",
        "date": "2026-09-27",
        "hash": "a" * 64,
        "verify_url": "https://digisign.example/verify?doc_id=abc123",
    }
    decoded = qr_module.decode_qr_image(qr_module.generate_qr_image(metadata))

    assert decoded is not None
    assert decoded["verify_url"].startswith("https://digisign.example/verify?")
    assert all(decoded[field] == value for field, value in metadata.items() if field != "verify_url")


def test_qr_verification_url_rejects_invalid_compressed_metadata():
    assert qr_module.decode_verification_query({"doc_id": "abc123", "m": "not-valid"}) is None


def test_qr_tampered_metadata_mismatch():
    original_metadata = {
        "doc_id": "doc001",
        "name": "Siti Aminah",
        "position": "Sekretaris",
        "institution": "Universitas Contoh",
        "date": "2026-09-27",
        "hash": "b" * 64
    }
    image = qr_module.generate_qr_image(original_metadata)
    decoded = qr_module.decode_qr_image(image)

    forged_metadata = dict(decoded)
    forged_metadata["hash"] = "c" * 64
    forged_metadata["name"] = "Penipu"

    assert forged_metadata["hash"] != original_metadata["hash"]
    assert forged_metadata["name"] != original_metadata["name"]


def test_qr_decode_invalid_image_returns_none():
    blank_image = Image.new("RGB", (100, 100), color="white")
    decoded = qr_module.decode_qr_image(blank_image)
    assert decoded is None


def test_qr_decode_from_multiple_images():
    metadata_list = [
        {"doc_id": "d1", "name": "A", "hash": "1" * 64},
        {"doc_id": "d2", "name": "B", "hash": "2" * 64}
    ]
    images = [qr_module.generate_qr_image(m) for m in metadata_list]
    decoded_list = qr_module.decode_qr_from_images(images)
    assert len(decoded_list) == 2
    doc_ids = [d["doc_id"] for d in decoded_list]
    assert "d1" in doc_ids
    assert "d2" in doc_ids
