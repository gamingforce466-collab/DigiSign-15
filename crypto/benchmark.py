"""Pengukuran waktu dan ukuran kriptografi.

RSA-2048-PSS adalah algoritma yang dipakai aplikasi. ECDSA P-256 hanya
pembanding ukuran dan kecepatan.
"""
import os
import tempfile
import time
import statistics
from datetime import datetime

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa, utils

from crypto import signer as signer_module
from crypto import verifier as verifier_module

DEFAULT_TRIALS = 30


def _stats(values_ms):
    return {
        "mean": statistics.mean(values_ms),
        "min": min(values_ms),
        "max": max(values_ms),
        "std": statistics.stdev(values_ms) if len(values_ms) > 1 else 0.0,
    }


def _rsa_case():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return {
        "name": "RSA-2048-PSS (dipakai aplikasi)",
        "key": key,
        "sign": signer_module.sign_digest,
        "verify": verifier_module.verify_digest,
    }


def _ecdsa_case():
    key = ec.generate_private_key(ec.SECP256R1())
    prehashed = ec.ECDSA(utils.Prehashed(hashes.SHA256()))

    def sign(private_key, digest):
        return private_key.sign(digest, prehashed)

    def verify(public_key, digest, signature):
        try:
            public_key.verify(signature, digest, prehashed)
            return True
        except Exception:
            return False

    return {"name": "ECDSA P-256 (pembanding)", "key": key, "sign": sign, "verify": verify}


def _sizes(key, signature):
    public = key.public_key()
    return {
        "signature_bytes": len(signature),
        "public_key_der_bytes": len(public.public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)),
        "public_key_pem_bytes": len(public.public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)),
    }


def run_benchmark(trials=DEFAULT_TRIALS):
    """Ukur waktu tanda tangan dan verifikasi sebanyak `trials` kali per algoritma."""
    if trials < 30:
        raise ValueError("Minimal 30 percobaan")
    digest = os.urandom(32)  # stand-in untuk hash SHA-256 dokumen
    results = []
    for case in (_rsa_case(), _ecdsa_case()):
        key, sign, verify = case["key"], case["sign"], case["verify"]
        public = key.public_key()
        signature = sign(key, digest)  # pemanasan, tidak dihitung
        verify(public, digest, signature)
        sign_ms, verify_ms = [], []
        for _ in range(trials):
            t0 = time.perf_counter()
            signature = sign(key, digest)
            sign_ms.append((time.perf_counter() - t0) * 1000)
            t0 = time.perf_counter()
            ok = verify(public, digest, signature)
            verify_ms.append((time.perf_counter() - t0) * 1000)
            if not ok:
                raise RuntimeError("Verifikasi gagal saat benchmark")
        results.append({
            "name": case["name"],
            "sign": _stats(sign_ms),
            "verify": _stats(verify_ms),
            "raw_sign": sign_ms,
            "raw_verify": verify_ms,
            "sizes": _sizes(key, signature),
        })
    return {"trials": trials, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "algorithms": results}


TAMPER_FRACTIONS = (0.0, 0.05, 0.15, 0.25, 0.35, 0.50, 0.65, 0.75, 0.90, 1.0)


def run_tamper_tests(count=10):
    """Uji tamper: ubah 1 byte PDF bertanda tangan di `count` posisi berbeda.

    Setiap skenario harus berstatus TAMPERED (hash berubah dan tanda tangan ditolak).
    Alur sama dengan aplikasi: hash SHA-256 seluruh byte PDF, tanda tangan RSA-2048-PSS.
    """
    import randomdata
    from pdf import handler as pdf_module

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    pdf_bytes, _ = randomdata.make_random_pdf_bytes()
    size = len(pdf_bytes)

    def digest_of(data):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "uji.pdf")
            with open(path, "wb") as f:
                f.write(data)
            return pdf_module.compute_content_digest(path)

    original_digest = digest_of(pdf_bytes)
    signature = signer_module.sign_digest(private_key, original_digest)
    control_ok = verifier_module.verify_digest(public_key, original_digest, signature)

    offsets = []
    for fraction in TAMPER_FRACTIONS[:count]:
        offset = min(int(size * fraction), size - 1)
        while offset in offsets:
            offset += 1
        offsets.append(offset)

    rows = []
    for number, offset in enumerate(offsets, start=1):
        tampered = bytearray(pdf_bytes)
        old = tampered[offset]
        tampered[offset] = old ^ 0x01  # ubah tepat 1 byte
        new_digest = digest_of(bytes(tampered))
        sig_ok = verifier_module.verify_digest(public_key, new_digest, signature)
        status = "VALID" if (sig_ok and new_digest == original_digest) else "TAMPERED"
        rows.append({
            "number": number,
            "offset": offset,
            "position_pct": round(offset / size * 100, 1),
            "old_byte": f"0x{old:02X}",
            "new_byte": f"0x{tampered[offset]:02X}",
            "new_digest": new_digest.hex(),
            "signature_valid": sig_ok,
            "status": status,
            "passed": status == "TAMPERED",
        })
    return {
        "pdf_size": size,
        "original_digest": original_digest.hex(),
        "control_valid": control_ok,
        "rows": rows,
        "all_passed": control_ok and all(r["passed"] for r in rows),
    }


def run_full(trials=DEFAULT_TRIALS):
    """Benchmark waktu + ukuran + uji tamper 1-byte (10 skenario)."""
    report = run_benchmark(trials)
    report["tamper"] = run_tamper_tests(10)
    return report


if __name__ == "__main__":
    # Jalankan dari terminal: python -m crypto.benchmark [jumlah_percobaan]
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TRIALS
    rep = run_benchmark(n)
    print(f"Benchmark {rep['trials']} percobaan (ms)")
    print(f"{'Algoritma':34}{'Operasi':14}{'Mean':>9}{'Min':>9}{'Maks':>9}{'Std':>9}")
    for a in rep["algorithms"]:
        for label, key in (("Tanda tangan", "sign"), ("Verifikasi", "verify")):
            st = a[key]
            print(f"{a['name']:34}{label:14}{st['mean']:9.4f}{st['min']:9.4f}{st['max']:9.4f}{st['std']:9.4f}")
    print()
    print(f"{'Algoritma':34}{'TTD (B)':>9}{'Pub DER (B)':>13}{'Pub PEM (B)':>13}")
    for a in rep["algorithms"]:
        z = a["sizes"]
        print(f"{a['name']:34}{z['signature_bytes']:9}{z['public_key_der_bytes']:13}{z['public_key_pem_bytes']:13}")
