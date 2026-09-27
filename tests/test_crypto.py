import sys
import os
import time
import statistics

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reportlab.pdfgen import canvas
from crypto import keys as key_module
from crypto import signer as signer_module
from crypto import verifier as verifier_module
from pdf import handler as pdf_module

TEST_OWNER = "pytest_owner_crypto"
TEST_PASSPHRASE = "pytest_passphrase_123"


def make_sample_pdf(path, text="Dokumen uji kriptografi digital signature"):
    c = canvas.Canvas(str(path))
    c.drawString(100, 750, text)
    c.save()


def setup_module(module):
    if not key_module.key_exists(TEST_OWNER):
        key_module.generate_keypair(TEST_OWNER, TEST_PASSPHRASE)


def test_key_generation_and_sizes():
    private_key = key_module.load_private_key(TEST_OWNER, TEST_PASSPHRASE)
    public_key = key_module.load_public_key(TEST_OWNER)
    public_pem = key_module.public_key_to_pem(public_key)
    assert private_key.key_size == 2048
    assert len(public_pem) > 0
    print(f"Ukuran kunci publik PEM: {len(public_pem)} bytes")


def test_signature_size(tmp_path):
    private_key = key_module.load_private_key(TEST_OWNER, TEST_PASSPHRASE)
    pdf_path = tmp_path / "sample.pdf"
    make_sample_pdf(pdf_path)
    digest = pdf_module.compute_content_digest(str(pdf_path))
    signature = signer_module.sign_digest(private_key, digest)
    assert len(signature) == 256
    print(f"Ukuran tanda tangan RSA-2048-PSS: {len(signature)} bytes")


def test_average_sign_verify_time(tmp_path):
    private_key = key_module.load_private_key(TEST_OWNER, TEST_PASSPHRASE)
    public_key = key_module.load_public_key(TEST_OWNER)
    pdf_path = tmp_path / "sample_timing.pdf"
    make_sample_pdf(pdf_path)
    digest = pdf_module.compute_content_digest(str(pdf_path))

    sign_times = []
    verify_times = []
    trials = 30

    for _ in range(trials):
        start = time.perf_counter()
        signature = signer_module.sign_digest(private_key, digest)
        sign_times.append(time.perf_counter() - start)

        start = time.perf_counter()
        valid = verifier_module.verify_digest(public_key, digest, signature)
        verify_times.append(time.perf_counter() - start)
        assert valid is True

    avg_sign = statistics.mean(sign_times)
    avg_verify = statistics.mean(verify_times)
    print(f"Rata-rata waktu tanda tangan ({trials}x): {avg_sign * 1000:.4f} ms")
    print(f"Rata-rata waktu verifikasi ({trials}x): {avg_verify * 1000:.4f} ms")
    assert avg_sign > 0
    assert avg_verify > 0
