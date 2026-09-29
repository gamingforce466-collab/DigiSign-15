"""Berkas serangan uji untuk tamper dan pemalsuan QR."""
import secrets
from pathlib import Path


def flip_one_byte(data):
    changed = bytearray(data)
    changed[len(changed) // 2] ^= 0x01
    return bytes(changed)


def make_fake_qr_pdf(documents_dir, verify_base_url, utc_now, randomdata, qr_module, pdf_module):
    base_bytes, _ = randomdata.make_random_pdf_bytes()
    fake_doc_id = secrets.token_hex(6)
    metadata = {
        "doc_id": fake_doc_id,
        "signer_id": secrets.token_hex(4),
        "name": randomdata.random_person_name(),
        "position": "Dekan Fakultas",
        "institution": "Universitas Contoh Nusantara",
        "date": utc_now().strftime("%Y-%m-%d"),
        "hash": secrets.token_hex(32),
        "verify_url": f"{verify_base_url}?doc_id={fake_doc_id}",
    }
    source = Path(documents_dir) / f"fake_src_{secrets.token_hex(4)}.pdf"
    output = Path(documents_dir) / f"fake_out_{secrets.token_hex(4)}.pdf"
    source.write_bytes(base_bytes)
    try:
        pdf_module.embed_qr_images(str(source), [qr_module.generate_qr_image(metadata)], str(output))
        return output.read_bytes(), metadata
    finally:
        source.unlink(missing_ok=True)
        output.unlink(missing_ok=True)


def paste_real_qr_on_other_pdf(signed_pdf_bytes, documents_dir, randomdata, pdf_module):
    documents_dir = Path(documents_dir)
    source_signed = documents_dir / f"paste_signed_{secrets.token_hex(4)}.pdf"
    source_other = documents_dir / f"paste_other_{secrets.token_hex(4)}.pdf"
    output = documents_dir / f"paste_out_{secrets.token_hex(4)}.pdf"
    source_signed.write_bytes(signed_pdf_bytes)
    other_bytes, _ = randomdata.make_random_pdf_bytes()
    source_other.write_bytes(other_bytes)
    try:
        images = pdf_module.extract_embedded_images(str(source_signed))
        pdf_module.embed_qr_images(str(source_other), images[:1], str(output))
        return output.read_bytes()
    finally:
        for path in (source_signed, source_other, output):
            path.unlink(missing_ok=True)