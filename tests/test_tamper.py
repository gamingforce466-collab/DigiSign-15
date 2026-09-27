import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reportlab.pdfgen import canvas
from crypto import keys as key_module
from crypto import signer as signer_module
from crypto import verifier as verifier_module
from pdf import handler as pdf_module

TEST_OWNER = "pytest_owner_tamper"
TEST_PASSPHRASE = "pytest_passphrase_456"
WRONG_OWNER = "pytest_owner_wrongkey"
WRONG_PASSPHRASE = "pytest_passphrase_789"


def make_sample_pdf(path, text):
    c = canvas.Canvas(str(path), pageCompression=0)
    c.drawString(100, 750, text)
    c.save()


def setup_module(module):
    if not key_module.key_exists(TEST_OWNER):
        key_module.generate_keypair(TEST_OWNER, TEST_PASSPHRASE)
    if not key_module.key_exists(WRONG_OWNER):
        key_module.generate_keypair(WRONG_OWNER, WRONG_PASSPHRASE)


def test_valid_document_passes(tmp_path):
    private_key = key_module.load_private_key(TEST_OWNER, TEST_PASSPHRASE)
    public_key = key_module.load_public_key(TEST_OWNER)
    pdf_path = tmp_path / "valid.pdf"
    make_sample_pdf(pdf_path, "Surat keterangan asli tanpa perubahan")
    digest = pdf_module.compute_content_digest(str(pdf_path))
    signature = signer_module.sign_digest(private_key, digest)
    assert verifier_module.verify_digest(public_key, digest, signature) is True


def test_tampered_document_fails(tmp_path):
    private_key = key_module.load_private_key(TEST_OWNER, TEST_PASSPHRASE)
    public_key = key_module.load_public_key(TEST_OWNER)
    original_path = tmp_path / "original.pdf"
    make_sample_pdf(original_path, "Surat keterangan sebelum diubah")
    original_digest = pdf_module.compute_content_digest(str(original_path))
    signature = signer_module.sign_digest(private_key, original_digest)

    tampered_path = tmp_path / "tampered.pdf"
    make_sample_pdf(tampered_path, "Surat keterangan sesudah diubah")
    tampered_digest = pdf_module.compute_content_digest(str(tampered_path))

    assert tampered_digest != original_digest
    assert verifier_module.verify_digest(public_key, tampered_digest, signature) is False


def test_byte_flip_tamper_detected(tmp_path):
    private_key = key_module.load_private_key(TEST_OWNER, TEST_PASSPHRASE)
    public_key = key_module.load_public_key(TEST_OWNER)
    original_path = tmp_path / "byteflip.pdf"
    marker = b"Dokumen untuk uji perubahan satu byte"
    make_sample_pdf(original_path, marker.decode("utf-8"))
    original_digest = pdf_module.compute_content_digest(str(original_path))
    signature = signer_module.sign_digest(private_key, original_digest)

    with open(original_path, "r+b") as f:
        data = bytearray(f.read())
        idx = bytes(data).find(marker)
        assert idx != -1
        data[idx] = data[idx] ^ 0xFF
        f.seek(0)
        f.write(data)
        f.truncate()

    try:
        new_digest = pdf_module.compute_content_digest(str(original_path))
        integrity_preserved = new_digest == original_digest
        signature_valid = verifier_module.verify_digest(public_key, new_digest, signature)
        result_ok = integrity_preserved and signature_valid
    except Exception:
        result_ok = False

    assert result_ok is False


def test_wrong_public_key_fails(tmp_path):
    private_key = key_module.load_private_key(TEST_OWNER, TEST_PASSPHRASE)
    wrong_public_key = key_module.load_public_key(WRONG_OWNER)
    pdf_path = tmp_path / "wrongkey.pdf"
    make_sample_pdf(pdf_path, "Dokumen untuk uji kunci publik yang salah")
    digest = pdf_module.compute_content_digest(str(pdf_path))
    signature = signer_module.sign_digest(private_key, digest)
    assert verifier_module.verify_digest(wrong_public_key, digest, signature) is False
