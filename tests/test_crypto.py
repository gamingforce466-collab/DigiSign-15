import sys
import os
import time
import statistics
<<<<<<< HEAD
import hashlib

import pytest
from cryptography.hazmat.primitives import serialization
=======
>>>>>>> e5f9e3f2d4901c926d7e0edf40d3f99ca6aad194

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
<<<<<<< HEAD


# ---------------------------------------------------------------------------
# Tes fungsi inti: keygen, hash, sign, verify, tamper
# ---------------------------------------------------------------------------

def test_keygen_private_key_is_encrypted_on_disk():
    private_path = key_module.KEYS_DIR / f"{TEST_OWNER}_private.pem"
    data = private_path.read_bytes()
    assert b"ENCRYPTED PRIVATE KEY" in data
    with pytest.raises(Exception):
        serialization.load_pem_private_key(data, password=b"passphrase_salah")
    with pytest.raises(TypeError):
        serialization.load_pem_private_key(data, password=None)


def test_hash_is_sha256_of_all_bytes(tmp_path):
    pdf_path = tmp_path / "hash.pdf"
    make_sample_pdf(pdf_path, "Uji hash")
    digest = pdf_module.compute_content_digest(str(pdf_path))
    assert len(digest) == 32
    assert digest == hashlib.sha256(pdf_path.read_bytes()).digest()


def test_sign_and_verify_roundtrip(tmp_path):
    private_key = key_module.load_private_key(TEST_OWNER, TEST_PASSPHRASE)
    public_key = key_module.load_public_key(TEST_OWNER)
    digest = hashlib.sha256(b"isi dokumen").digest()
    signature = signer_module.sign_digest(private_key, digest)
    assert verifier_module.verify_digest(public_key, digest, signature) is True


def test_pss_signature_is_randomized():
    private_key = key_module.load_private_key(TEST_OWNER, TEST_PASSPHRASE)
    digest = hashlib.sha256(b"dokumen sama").digest()
    assert signer_module.sign_digest(private_key, digest) != signer_module.sign_digest(private_key, digest)


def test_tamper_one_byte_fails_verification(tmp_path):
    private_key = key_module.load_private_key(TEST_OWNER, TEST_PASSPHRASE)
    public_key = key_module.load_public_key(TEST_OWNER)
    pdf_path = tmp_path / "tamper.pdf"
    make_sample_pdf(pdf_path, "Dokumen sebelum diubah")
    signature = signer_module.sign_digest(private_key, pdf_module.compute_content_digest(str(pdf_path)))
    data = bytearray(pdf_path.read_bytes())
    data[len(data) // 2] ^= 0x01
    pdf_path.write_bytes(bytes(data))
    new_digest = pdf_module.compute_content_digest(str(pdf_path))
    assert verifier_module.verify_digest(public_key, new_digest, signature) is False


def test_corrupted_signature_is_rejected():
    private_key = key_module.load_private_key(TEST_OWNER, TEST_PASSPHRASE)
    public_key = key_module.load_public_key(TEST_OWNER)
    digest = hashlib.sha256(b"dokumen").digest()
    signature = bytearray(signer_module.sign_digest(private_key, digest))
    signature[0] ^= 0x01
    assert verifier_module.verify_digest(public_key, digest, bytes(signature)) is False
    assert verifier_module.verify_digest(public_key, digest, b"") is False


def test_benchmark_30_trials_stats_and_sizes():
    from crypto import benchmark
    report = benchmark.run_benchmark(30)
    assert report["trials"] == 30
    rsa_r, ec_r = report["algorithms"]
    for algo in (rsa_r, ec_r):
        assert len(algo["raw_sign"]) == 30 and len(algo["raw_verify"]) == 30
        for op in ("sign", "verify"):
            st = algo[op]
            assert st["min"] <= st["mean"] <= st["max"] and st["std"] >= 0
    assert rsa_r["sizes"]["signature_bytes"] == 256
    assert rsa_r["sizes"]["public_key_der_bytes"] == 294
    assert ec_r["sizes"]["signature_bytes"] < rsa_r["sizes"]["signature_bytes"]
    tamper = benchmark.run_tamper_tests(10)
    assert len(tamper["rows"]) == 10 and tamper["control_valid"] is True
    assert all(r["status"] == "TAMPERED" and not r["signature_valid"] for r in tamper["rows"])
    with pytest.raises(ValueError):
        benchmark.run_benchmark(10)
=======
>>>>>>> e5f9e3f2d4901c926d7e0edf40d3f99ca6aad194
