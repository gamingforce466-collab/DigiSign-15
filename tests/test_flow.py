import io
import sys
import os
import json
import hashlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from reportlab.pdfgen import canvas

import app as app_module
from crypto import keys as key_module

OWNER_A = "pytest_flow_owner_a"
OWNER_B = "pytest_flow_owner_b"
PASS_A = "pytest_flow_pass_a"
PASS_B = "pytest_flow_pass_b"


def make_pdf_bytes(text):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, text)
    c.save()
    return buf.getvalue()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    docs = tmp_path / "documents"
    sigs = tmp_path / "signatures"
    docs.mkdir()
    sigs.mkdir()
    monkeypatch.setattr(app_module, "DOCUMENTS_DIR", docs)
    monkeypatch.setattr(app_module, "SIGNATURES_DIR", sigs)
    for owner, pw in ((OWNER_A, PASS_A), (OWNER_B, PASS_B)):
        if not key_module.key_exists(owner):
            key_module.generate_keypair(owner, pw)
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client(), docs, sigs


def sign(client, owner, passphrase, name, pdf_bytes=None, doc_id=""):
    data = {
        "doc_id": doc_id,
        "owner_id": owner,
        "passphrase": passphrase,
        "signer_name": name,
        "position": "Ketua",
        "institution": "Univ Uji",
    }
    if pdf_bytes is not None:
        data["document"] = (io.BytesIO(pdf_bytes), "surat.pdf")
    return client.post("/sign", data=data, content_type="multipart/form-data")


def verify(client, pdf_bytes, doc_id):
    resp = client.post(
        "/verify",
        data={"doc_id": doc_id, "document": (io.BytesIO(pdf_bytes), "cek.pdf")},
        content_type="multipart/form-data",
    )
    return resp.get_data(as_text=True)


def only_doc_id(sigs):
    files = list(sigs.glob("*.json"))
    assert len(files) == 1
    return files[0].stem


def test_sign_then_verify_signed_pdf_passes(client):
    c, docs, sigs = client
    sign(c, OWNER_A, PASS_A, "Budi", make_pdf_bytes("Surat keterangan"))
    doc_id = only_doc_id(sigs)
    signed = (docs / f"{doc_id}_signed.pdf").read_bytes()
    html = verify(c, signed, doc_id)
    assert "UTUH" in html
    assert "DIUBAH / TIDAK COCOK" not in html
    assert "TIDAK VALID" not in html


def test_one_byte_change_in_signed_pdf_fails(client):
    c, docs, sigs = client
    sign(c, OWNER_A, PASS_A, "Budi", make_pdf_bytes("Surat keterangan"))
    doc_id = only_doc_id(sigs)
    signed = bytearray((docs / f"{doc_id}_signed.pdf").read_bytes())
    signed[len(signed) // 2] ^= 0x01
    record = json.loads((sigs / f"{doc_id}.json").read_text())
    assert record["signed_hashes"]
    assert hashlib.sha256(bytes(signed)).hexdigest() not in record["signed_hashes"]
    html = verify(c, bytes(signed), doc_id)
    assert "DIUBAH / TIDAK COCOK" in html
    assert "TIDAK VALID" in html


def test_multi_signer_keeps_all_versions_valid(client):
    c, docs, sigs = client
    sign(c, OWNER_A, PASS_A, "Budi", make_pdf_bytes("Lembar pengesahan"))
    doc_id = only_doc_id(sigs)
    version1 = (docs / f"{doc_id}_signed.pdf").read_bytes()
    sign(c, OWNER_B, PASS_B, "Siti", doc_id=doc_id)
    version2 = (docs / f"{doc_id}_signed.pdf").read_bytes()
    assert version1 != version2
    record = json.loads((sigs / f"{doc_id}.json").read_text())
    assert len(record["signers"]) == 2
    assert len(record["signed_hashes"]) == 2
    assert hashlib.sha256(version1).hexdigest() in app_module.known_hashes(record)
    assert hashlib.sha256(version2).hexdigest() in app_module.known_hashes(record)
    for version in (version1, version2):
        html = verify(c, version, doc_id)
        assert "UTUH" in html and "TIDAK VALID" not in html
