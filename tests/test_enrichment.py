import io
import sys
import os
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from pypdf import PdfReader

import app as app_module
import randomdata
from crypto import keys as key_module
from pdf import handler as pdf_module
from qr import generator as qr_module

OWNER_A = "pytest_enrich_owner_a"
OWNER_B = "pytest_enrich_owner_b"
PASS_A = "pytest_enrich_pass_a"
PASS_B = "pytest_enrich_pass_b"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    docs = tmp_path / "documents"
    sigs = tmp_path / "signatures"
    docs.mkdir()
    sigs.mkdir()
    monkeypatch.setattr(app_module, "DOCUMENTS_DIR", docs)
    monkeypatch.setattr(app_module, "SIGNATURES_DIR", sigs)
    monkeypatch.delenv("ENABLE_TEST_TOOLS", raising=False)
    for owner, pw in ((OWNER_A, PASS_A), (OWNER_B, PASS_B)):
        if not key_module.key_exists(owner):
            key_module.generate_keypair(owner, pw)
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client(), docs, sigs


def status_block(code):
    return f'<p class="text-2xl font-bold">{code}</p>'


STATUS_VALID = status_block("VALID")


def post_sign(client, owner, passphrase, name, pdf_bytes=None, doc_id="", **extra):
    data = {
        "doc_id": doc_id, "owner_id": owner, "passphrase": passphrase,
        "signer_name": name, "position": "Ketua", "institution": "Univ Uji",
        "signed_date": "2026-09-28",
    }
    data.update(extra)
    if pdf_bytes is not None:
        data["document"] = (io.BytesIO(pdf_bytes), "surat.pdf")
    return client.post("/sign", data=data, content_type="multipart/form-data")


def only_doc_id(sigs):
    files = list(sigs.glob("*.json"))
    assert len(files) == 1
    return files[0].stem


def last_page_text(path):
    return PdfReader(str(path)).pages[-1].extract_text()


def test_two_signers_produce_two_labeled_blocks_and_two_qr(client):
    c, docs, sigs = client
    pdf_bytes, _ = randomdata.make_random_pdf_bytes()
    post_sign(c, OWNER_A, PASS_A, "Budi Santoso", pdf_bytes)
    doc_id = only_doc_id(sigs)
    post_sign(c, OWNER_B, PASS_B, "Siti Aminah", doc_id=doc_id)
    signed = docs / f"{doc_id}_signed.pdf"

    text = last_page_text(signed)
    assert "TANDA TANGAN DIGITAL #1" in text
    assert "TANDA TANGAN DIGITAL #2" in text
    assert "Budi Santoso" in text and "Siti Aminah" in text

    decoded = qr_module.decode_qr_from_images(pdf_module.extract_embedded_images(str(signed)))
    assert sorted(d["name"] for d in decoded) == ["Budi Santoso", "Siti Aminah"]


def test_verify_page_shows_two_of_two_and_earlier_version_one_of_two(client):
    c, docs, sigs = client
    pdf_bytes, _ = randomdata.make_random_pdf_bytes()
    post_sign(c, OWNER_A, PASS_A, "Budi Santoso", pdf_bytes)
    doc_id = only_doc_id(sigs)
    v1 = (docs / f"{doc_id}_signed.pdf").read_bytes()
    post_sign(c, OWNER_B, PASS_B, "Siti Aminah", doc_id=doc_id)
    v2 = (docs / f"{doc_id}_signed.pdf").read_bytes()

    def verify(data):
        return c.post("/verify", data={"doc_id": "", "document": (io.BytesIO(data), "x.pdf")},
                      content_type="multipart/form-data").get_data(as_text=True)

    html2 = verify(v2)
    assert "<b>2 dari 2</b>" in html2
    assert STATUS_VALID in html2

    html1 = verify(v1)
    assert "<b>1 dari 2</b>" in html1
    assert "UTUH" in html1


def test_unknown_doc_id_is_rejected_not_silently_created(client):
    c, docs, sigs = client
    pdf_bytes, _ = randomdata.make_random_pdf_bytes()
    resp = post_sign(c, OWNER_A, PASS_A, "Budi", pdf_bytes, doc_id="abcdef123456", follow_redirects=True) \
        if False else c.post("/sign", data={
            "doc_id": "abcdef123456", "owner_id": OWNER_A, "passphrase": PASS_A, "signer_name": "Budi",
            "document": (io.BytesIO(pdf_bytes), "surat.pdf")},
            content_type="multipart/form-data", follow_redirects=True)
    assert "tidak ditemukan" in resp.get_data(as_text=True)
    assert list(sigs.glob("*.json")) == []


def test_doc_id_path_traversal_is_ignored(client):
    assert app_module.load_signature_record("../../etc/passwd") is None
    assert app_module.valid_doc_id("0123456789ab") is True
    assert app_module.valid_doc_id("../x") is False


def test_sample_pdf_option_is_gone(client):
    c, docs, sigs = client
    resp = c.post("/sign", data={"doc_id": "", "owner_id": OWNER_A, "passphrase": PASS_A,
                                 "signer_name": "Budi", "use_sample_pdf": "1"},
                  content_type="multipart/form-data", follow_redirects=True)
    assert "Unggah berkas PDF" in resp.get_data(as_text=True)
    assert list(sigs.glob("*.json")) == []


def test_invalid_pdf_upload_is_rejected(client):
    c, docs, sigs = client
    resp = c.post("/sign", data={
        "doc_id": "", "owner_id": OWNER_A, "passphrase": PASS_A, "signer_name": "Budi",
        "document": (io.BytesIO(b"bukan pdf"), "x.pdf")},
        content_type="multipart/form-data", follow_redirects=True)
    assert "bukan PDF yang valid" in resp.get_data(as_text=True)
    assert list(sigs.glob("*.json")) == []


def test_random_api_returns_form_data(client):
    c, _, _ = client
    data = c.get("/api/random").get_json()
    for key in ("signer_name", "position", "institution", "signed_date", "owner_id", "passphrase"):
        assert data[key]
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", data["signed_date"])


def test_random_key_api_creates_usable_key(client):
    c, _, _ = client
    data = c.post("/api/random_key").get_json()
    try:
        assert key_module.key_exists(data["owner_id"])
        assert key_module.load_private_key(data["owner_id"], data["passphrase"]).key_size == 2048
    finally:
        key_module.delete_keypair(data["owner_id"])


def test_test_tools_can_be_disabled(client, monkeypatch):
    c, _, _ = client
    monkeypatch.setenv("ENABLE_TEST_TOOLS", "0")
    assert c.get("/api/random").status_code == 404
    assert c.post("/api/random_key").status_code == 404


def test_many_signers_wrap_to_next_row_and_stay_readable(client):
    c, docs, sigs = client
    pdf_bytes, _ = randomdata.make_random_pdf_bytes()
    post_sign(c, OWNER_A, PASS_A, "Penandatangan Satu", pdf_bytes)
    doc_id = only_doc_id(sigs)
    for n in range(2, 6):
        owner, pw = (OWNER_B, PASS_B) if n % 2 == 0 else (OWNER_A, PASS_A)
        post_sign(c, owner, pw, f"Penandatangan {n}", doc_id=doc_id)
    signed = docs / f"{doc_id}_signed.pdf"
    text = last_page_text(signed)
    for n in range(1, 6):
        assert f"TANDA TANGAN DIGITAL #{n}" in text
    decoded = qr_module.decode_qr_from_images(pdf_module.extract_embedded_images(str(signed)))
    assert len(decoded) == 5


def test_qr_decode_is_reliable_for_realistic_payloads():
    """Regresi: detektor QR bawaan OpenCV gagal ~50% pada payload sepanjang ini."""
    import uuid
    failures = 0
    for _ in range(40):
        metadata = {
            "doc_id": uuid.uuid4().hex[:12], "signer_id": uuid.uuid4().hex[:8],
            "name": "Budi Santoso", "position": "Ketua Panitia",
            "institution": "Universitas Contoh Nusantara", "date": "2026-09-28",
            "hash": uuid.uuid4().hex + uuid.uuid4().hex,
            "verify_url": "http://localhost:5000/verify?doc_id=abc",
        }
        decoded = qr_module.decode_qr_image(qr_module.generate_qr_image(metadata))
        if decoded is None or decoded["signer_id"] != metadata["signer_id"]:
            failures += 1
    assert failures == 0
