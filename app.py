import os
<<<<<<< HEAD
import re
import json
import uuid
import base64
import secrets
from io import BytesIO
from pathlib import Path
from datetime import datetime, timezone
from flask import (
    Flask, render_template, request, redirect, url_for,
    send_from_directory, send_file, flash, jsonify, abort
)
=======
import json
import uuid
import base64
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
>>>>>>> e5f9e3f2d4901c926d7e0edf40d3f99ca6aad194
from dotenv import load_dotenv

from crypto import keys as key_module
from crypto import signer as signer_module
from crypto import verifier as verifier_module
<<<<<<< HEAD
from crypto import benchmark as benchmark_module
from pdf import handler as pdf_module
from qr import generator as qr_module
import randomdata
=======
from pdf import handler as pdf_module
from qr import generator as qr_module
>>>>>>> e5f9e3f2d4901c926d7e0edf40d3f99ca6aad194

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DOCUMENTS_DIR = BASE_DIR / "storage" / "documents"
SIGNATURES_DIR = BASE_DIR / "storage" / "signatures"
KEYS_DIR = BASE_DIR / "storage" / "keys"
for d in (DOCUMENTS_DIR, SIGNATURES_DIR, KEYS_DIR):
    d.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_fallback_secret_key")
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

VERIFY_BASE_URL = os.environ.get("VERIFY_BASE_URL", "http://localhost:5000/verify")

<<<<<<< HEAD
DOC_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")
OWNER_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,40}$")

# Kode status hasil verifikasi
STATUS_INFO = {
    "VALID": ("VALID", "Dokumen utuh dan semua tanda tangan cocok."),
    "TAMPERED": ("TAMPERED", "Isi dokumen berbeda dari yang ditandatangani. Ditolak."),
    "KEY_MISMATCH": ("KEY_MISMATCH", "Dokumen utuh, tetapi kunci publik tidak cocok dengan tanda tangan. Ditolak."),
    "QR_FORGED": ("QR_FORGED", "QR-Code tidak terdaftar atau datanya tidak cocok. Ditolak."),
    "NOT_FOUND": ("NOT_FOUND", "Doc ID tidak ditemukan. Ditolak."),
    "NO_QR": ("NO_QR", "QR-Code tidak terbaca dan Doc ID tidak diisi."),
}

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_tools_enabled():
    """Uji otomatis aktif secara bawaan. Set ENABLE_TEST_TOOLS=0 untuk mematikan."""
    return os.environ.get("ENABLE_TEST_TOOLS", "1") != "0"


@app.context_processor
def inject_flags():
    return {"test_tools": test_tools_enabled(), "status_info": STATUS_INFO}


def valid_doc_id(doc_id):
    return bool(doc_id and DOC_ID_PATTERN.match(doc_id))

=======
>>>>>>> e5f9e3f2d4901c926d7e0edf40d3f99ca6aad194

def signature_record_path(doc_id):
    return SIGNATURES_DIR / f"{doc_id}.json"


def load_signature_record(doc_id):
<<<<<<< HEAD
    if not valid_doc_id(doc_id):
        return None
=======
>>>>>>> e5f9e3f2d4901c926d7e0edf40d3f99ca6aad194
    path = signature_record_path(doc_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_signature_record(doc_id, record):
    path = signature_record_path(doc_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)


def known_hashes(record):
    """Hash sah suatu dokumen: berkas asli + setiap versi berkas bertanda tangan (bertambah tiap penandatangan)."""
    return {record["content_hash_hex"], *record.get("signed_hashes", [])}


def list_signature_records():
    records = []
    for path in sorted(SIGNATURES_DIR.glob("*.json")):
        with open(path, "r", encoding="utf-8") as f:
            records.append(json.load(f))
<<<<<<< HEAD
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return records


# ---------------------------------------------------------------------------
# Penandatanganan (dipakai oleh halaman /sign dan uji otomatis)
# ---------------------------------------------------------------------------

class SigningError(Exception):
    pass


def perform_signing(owner_id, passphrase, signer_name, position="", institution="",
                    signed_date=None, doc_id="", pdf_bytes=None, original_filename=None):
    """Tambahkan satu penandatangan.

    - doc_id kosong  -> dokumen baru, `pdf_bytes` wajib.
    - doc_id terisi  -> tambah penandatangan pada dokumen tersebut (doc_id harus sudah ada).
    Kembalikan (doc_id, record). Semua QR-Code penandatangan digambar ulang pada PDF asli
    sehingga berkas akhir memuat seluruh tanda tangan.
    """
    if not owner_id or not passphrase or not signer_name:
        raise SigningError("Kunci, passphrase, dan nama penandatangan wajib diisi")

    if not OWNER_PATTERN.match(owner_id):
        raise SigningError("Nama kunci tidak valid")
    try:
        private_key = key_module.load_private_key(owner_id, passphrase)
    except Exception:
        raise SigningError("Passphrase salah atau kunci tidak ditemukan")

    signed_date = signed_date or utc_now().strftime("%Y-%m-%d")

    if doc_id:
        record = load_signature_record(doc_id)
        if record is None:
            raise SigningError(f"Doc ID {doc_id} tidak ditemukan. Pilih dokumen dari daftar")
        original_path = DOCUMENTS_DIR / f"{doc_id}_original.pdf"
        if not original_path.exists():
            raise SigningError("Berkas asli dokumen tidak ada di server")
        content_digest = bytes.fromhex(record["content_hash_hex"])
        if pdf_bytes:
            temp_check_path = DOCUMENTS_DIR / f"{doc_id}_check_{uuid.uuid4().hex[:8]}.pdf"
            temp_check_path.write_bytes(pdf_bytes)
            try:
                new_digest = pdf_module.compute_content_digest(str(temp_check_path))
            finally:
                temp_check_path.unlink(missing_ok=True)
            if new_digest.hex() not in known_hashes(record):
                raise SigningError("Isi PDF tidak cocok dengan dokumen asli. Penandatanganan dibatalkan")
    else:
        if not pdf_bytes:
            raise SigningError("Unggah berkas PDF untuk dokumen baru")
        if not pdf_module.is_valid_pdf_bytes(pdf_bytes):
            raise SigningError("Berkas bukan PDF yang valid")
        doc_id = uuid.uuid4().hex[:12]
        original_path = DOCUMENTS_DIR / f"{doc_id}_original.pdf"
        original_path.write_bytes(pdf_bytes)
        content_digest = pdf_module.compute_content_digest(str(original_path))
        record = {
            "doc_id": doc_id,
            "original_filename": original_filename or "dokumen.pdf",
            "content_hash_hex": content_digest.hex(),
            "signed_hashes": [],
            "created_at": utc_now().isoformat(),
            "signers": []
        }

    signature = signer_module.sign_digest(private_key, content_digest)
    public_key_pem = key_module.public_key_to_pem(private_key.public_key()).decode("utf-8")

    record["signers"].append({
        "signer_id": uuid.uuid4().hex[:8],
        "owner_id": owner_id,
        "signer_name": signer_name,
        "position": position,
        "institution": institution,
        "signed_date": signed_date,
        "algorithm": "RSA-2048-PSS-SHA256",
        "public_key_pem": public_key_pem,
        "signature_b64": base64.b64encode(signature).decode("utf-8")
    })

    qr_images = []
    block_infos = []
    for entry in record["signers"]:
        metadata = {
            "doc_id": doc_id,
            "signer_id": entry["signer_id"],
            "name": entry["signer_name"],
            "position": entry["position"],
            "institution": entry["institution"],
            "date": entry["signed_date"],
            "hash": record["content_hash_hex"],
            "verify_url": f"{VERIFY_BASE_URL}?doc_id={doc_id}"
        }
        qr_images.append(qr_module.generate_qr_image(metadata))
        block_infos.append({
            "name": entry["signer_name"],
            "position": entry["position"],
            "institution": entry["institution"],
            "date": entry["signed_date"],
        })

    signed_output_path = DOCUMENTS_DIR / f"{doc_id}_signed.pdf"
    pdf_module.embed_qr_images(str(original_path), qr_images, str(signed_output_path), signers=block_infos)

    signed_hash_hex = pdf_module.compute_content_digest(str(signed_output_path)).hex()
    record.setdefault("signed_hashes", []).append(signed_hash_hex)
    save_signature_record(doc_id, record)
    return doc_id, record


# ---------------------------------------------------------------------------
# Verifikasi (dipakai oleh halaman /verify dan uji otomatis)
# ---------------------------------------------------------------------------

def decide_status(integrity_ok, signers, qr_forged):
    if not integrity_ok:
        return "TAMPERED"
    if qr_forged:
        return "QR_FORGED"
    if not signers or not all(x["signature_valid"] for x in signers):
        return "KEY_MISMATCH"
    return "VALID"


def compute_verification(pdf_path, manual_doc_id="", override_public_key=None):
    try:
        images = pdf_module.extract_embedded_images(str(pdf_path))
        decoded_list = qr_module.decode_qr_from_images(images)
    except Exception:
        decoded_list = []

    doc_id = manual_doc_id
    from_qr = False
    if not doc_id and decoded_list:
        candidates = [d.get("doc_id", "") for d in decoded_list if isinstance(d, dict) and d.get("doc_id")]
        registered = [c for c in candidates if DOC_ID_PATTERN.match(c) and load_signature_record(c)]
        doc_id = (registered or candidates or [""])[0]
        from_qr = bool(doc_id)

    if not doc_id:
        return {"status": "NO_QR",
                "error": "Doc ID tidak ditemukan: QR-Code tidak terbaca dan Doc ID tidak diisi"}

    record = load_signature_record(doc_id)
    if record is None:
        return {"status": "QR_FORGED" if from_qr else "NOT_FOUND",
                "doc_id": doc_id,
                "error": ("QR-Code memuat Doc ID yang tidak terdaftar, kemungkinan QR palsu"
                          if from_qr else f"Doc ID {doc_id} tidak ditemukan")}

    try:
        current_digest = pdf_module.compute_content_digest(str(pdf_path))
    except Exception:
        current_digest = None

    stored_digest = bytes.fromhex(record["content_hash_hex"])
    integrity_ok = current_digest is not None and current_digest.hex() in known_hashes(record)

    qr_by_signer = {
        d.get("signer_id"): d for d in decoded_list
        if isinstance(d, dict) and d.get("doc_id") == doc_id
    }

    signer_results = []
    for number, entry in enumerate(record["signers"], start=1):
        public_key = override_public_key if override_public_key else key_module.load_public_key_from_pem(
            entry["public_key_pem"].encode("utf-8")
        )
        signature_bytes = base64.b64decode(entry["signature_b64"])
        if integrity_ok:
            sig_valid = verifier_module.verify_digest(public_key, stored_digest, signature_bytes)
        else:
            sig_valid = False

        qr = qr_by_signer.get(entry["signer_id"])
        if qr is None:
            qr_status = "missing"
        elif (qr.get("hash") == record["content_hash_hex"]
              and qr.get("name") == entry["signer_name"]
              and qr.get("date") == entry["signed_date"]):
            qr_status = "ok"
        else:
            qr_status = "mismatch"

        signer_results.append({
            "number": number,
            "signer_id": entry["signer_id"],
            "signer_name": entry["signer_name"],
            "position": entry["position"],
            "institution": entry["institution"],
            "signed_date": entry["signed_date"],
            "signature_valid": sig_valid,
            "qr_status": qr_status
        })

    qr_forged = any(x["qr_status"] == "mismatch" for x in signer_results)
    status = decide_status(integrity_ok, signer_results, qr_forged)
    return {
        "status": status,
        "doc_id": doc_id,
        "original_filename": record.get("original_filename", ""),
        "integrity_ok": integrity_ok,
        "signers": signer_results,
        "signers_total": len(signer_results),
        "signers_in_document": sum(1 for s in signer_results if s["qr_status"] == "ok"),
        "qr_metadata_found": decoded_list,
        "overall_valid": status == "VALID"
    }


def verify_pdf_bytes(data, manual_doc_id="", override_public_key=None):
    temp_path = DOCUMENTS_DIR / f"verify_temp_{uuid.uuid4().hex[:8]}.pdf"
    temp_path.write_bytes(data)
    try:
        return compute_verification(temp_path, manual_doc_id, override_public_key)
    finally:
        temp_path.unlink(missing_ok=True)


def flip_one_byte(data):
    tampered = bytearray(data)
    tampered[len(tampered) // 2] ^= 0x01
    return bytes(tampered)


def make_fake_qr_pdf():
    """PDF baru yang belum pernah ditandatangani, ditempeli gambar QR-Code buatan sendiri.

    Isi QR meniru metadata asli (nama, hash, tautan), tetapi Doc ID-nya tidak terdaftar.
    Kembalikan (bytes, metadata_palsu).
    """
    base_bytes, _ = randomdata.make_random_pdf_bytes()
    fake_doc_id = secrets.token_hex(6)
    fake = {
        "doc_id": fake_doc_id,
        "signer_id": secrets.token_hex(4),
        "name": randomdata.random_person_name(),
        "position": "Dekan Fakultas",
        "institution": "Universitas Contoh Nusantara",
        "date": utc_now().strftime("%Y-%m-%d"),
        "hash": secrets.token_hex(32),
        "verify_url": f"{VERIFY_BASE_URL}?doc_id={fake_doc_id}",
    }
    src = DOCUMENTS_DIR / f"fake_src_{secrets.token_hex(4)}.pdf"
    out = DOCUMENTS_DIR / f"fake_out_{secrets.token_hex(4)}.pdf"
    src.write_bytes(base_bytes)
    try:
        pdf_module.embed_qr_images(str(src), [qr_module.generate_qr_image(fake)], str(out))
        return out.read_bytes(), fake
    finally:
        src.unlink(missing_ok=True)
        out.unlink(missing_ok=True)


def paste_real_qr_on_other_pdf(signed_pdf_bytes):
    """Ambil QR-Code asli dari PDF bertanda tangan, tempel ke PDF lain yang tidak pernah ditandatangani."""
    src_signed = DOCUMENTS_DIR / f"paste_signed_{secrets.token_hex(4)}.pdf"
    src_other = DOCUMENTS_DIR / f"paste_other_{secrets.token_hex(4)}.pdf"
    out = DOCUMENTS_DIR / f"paste_out_{secrets.token_hex(4)}.pdf"
    src_signed.write_bytes(signed_pdf_bytes)
    other_bytes, _ = randomdata.make_random_pdf_bytes()
    src_other.write_bytes(other_bytes)
    try:
        images = pdf_module.extract_embedded_images(str(src_signed))
        pdf_module.embed_qr_images(str(src_other), images[:1], str(out))
        return out.read_bytes()
    finally:
        for f in (src_signed, src_other, out):
            f.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Halaman utama
# ---------------------------------------------------------------------------

=======
    return records


>>>>>>> e5f9e3f2d4901c926d7e0edf40d3f99ca6aad194
@app.route("/")
def index():
    records = list_signature_records()
    key_owners = key_module.list_keys()
    total_signers = sum(len(r.get("signers", [])) for r in records)
    return render_template(
        "index.html",
        records=records,
        key_owners=key_owners,
        total_documents=len(records),
        total_signers=total_signers
    )


<<<<<<< HEAD
def clear_storage():
    """Hapus semua dokumen, data tanda tangan, dan kunci. Kembalikan jumlah berkas terhapus."""
    counts = {"documents": 0, "signatures": 0, "keys": 0}
    for name, folder in (("documents", DOCUMENTS_DIR), ("signatures", SIGNATURES_DIR),
                         ("keys", key_module.KEYS_DIR)):
        for path in Path(folder).glob("*"):
            if path.is_file() and path.name != ".gitkeep":
                path.unlink(missing_ok=True)
                counts[name] += 1
    return counts


@app.route("/clear", methods=["POST"])
def clear_all():
    counts = clear_storage()
    flash(f"Data dibersihkan: {counts['documents']} PDF, {counts['signatures']} data tanda tangan, "
          f"{counts['keys']} berkas kunci", "success")
    return redirect(url_for("index"))


=======
>>>>>>> e5f9e3f2d4901c926d7e0edf40d3f99ca6aad194
@app.route("/generate_keys", methods=["POST"])
def generate_keys():
    owner_id = request.form.get("owner_id", "").strip()
    passphrase = request.form.get("passphrase", "")
    if not owner_id or not passphrase:
<<<<<<< HEAD
        flash("Nama kunci dan passphrase wajib diisi", "error")
        return redirect(url_for("sign_page"))
    if not OWNER_PATTERN.match(owner_id):
        flash("Nama kunci hanya boleh huruf, angka, _ dan - (maks 40 karakter)", "error")
        return redirect(url_for("sign_page"))
    if key_module.key_exists(owner_id):
        flash("Nama kunci sudah dipakai", "error")
        return redirect(url_for("sign_page"))
    key_module.generate_keypair(owner_id, passphrase)
    flash(f"Kunci RSA-2048 '{owner_id}' berhasil dibuat", "success")
=======
        flash("Nama pemilik kunci dan passphrase wajib diisi", "error")
        return redirect(url_for("sign_page"))
    if key_module.key_exists(owner_id):
        flash("Kunci dengan nama tersebut sudah ada", "error")
        return redirect(url_for("sign_page"))
    key_module.generate_keypair(owner_id, passphrase)
    flash(f"Pasangan kunci RSA 2048-bit untuk {owner_id} berhasil dibuat", "success")
>>>>>>> e5f9e3f2d4901c926d7e0edf40d3f99ca6aad194
    return redirect(url_for("sign_page"))


@app.route("/sign", methods=["GET", "POST"])
def sign_page():
    key_owners = key_module.list_keys()
    if request.method == "GET":
<<<<<<< HEAD
        return render_template(
            "sign.html",
            key_owners=key_owners,
            records=list_signature_records(),
            prefill_doc_id=request.args.get("doc_id", "").strip()
        )
=======
        return render_template("sign.html", key_owners=key_owners)
>>>>>>> e5f9e3f2d4901c926d7e0edf40d3f99ca6aad194

    doc_id = request.form.get("doc_id", "").strip()
    owner_id = request.form.get("owner_id", "").strip()
    passphrase = request.form.get("passphrase", "")
    signer_name = request.form.get("signer_name", "").strip()
    position = request.form.get("position", "").strip()
    institution = request.form.get("institution", "").strip()
<<<<<<< HEAD
    signed_date = request.form.get("signed_date") or utc_now().strftime("%Y-%m-%d")
    uploaded_file = request.files.get("document")

    pdf_bytes = None
    original_filename = None
    if uploaded_file and uploaded_file.filename:
        pdf_bytes = uploaded_file.read()
        original_filename = uploaded_file.filename

    try:
        doc_id, record = perform_signing(
            owner_id, passphrase, signer_name, position, institution, signed_date,
            doc_id=doc_id, pdf_bytes=pdf_bytes, original_filename=original_filename
        )
    except SigningError as exc:
        flash(str(exc), "error")
        return redirect(url_for("sign_page", doc_id=doc_id) if doc_id else url_for("sign_page"))

    flash(f"Dokumen ditandatangani ({len(record['signers'])} penandatangan)", "success")
    return render_template(
        "sign.html",
        key_owners=key_owners,
        records=list_signature_records(),
        prefill_doc_id=doc_id,
=======
    signed_date = request.form.get("signed_date") or datetime.utcnow().strftime("%Y-%m-%d")
    uploaded_file = request.files.get("document")

    if not owner_id or not passphrase or not signer_name:
        flash("Kunci penandatangan, passphrase, dan nama penandatangan wajib diisi", "error")
        return redirect(url_for("sign_page"))

    try:
        private_key = key_module.load_private_key(owner_id, passphrase)
    except Exception:
        flash("Passphrase salah atau kunci privat tidak ditemukan", "error")
        return redirect(url_for("sign_page"))

    is_new_document = not doc_id or load_signature_record(doc_id) is None

    if is_new_document:
        if not uploaded_file or uploaded_file.filename == "":
            flash("Berkas PDF wajib diunggah untuk dokumen baru", "error")
            return redirect(url_for("sign_page"))
        doc_id = uuid.uuid4().hex[:12]
        original_path = DOCUMENTS_DIR / f"{doc_id}_original.pdf"
        uploaded_file.save(str(original_path))
        content_digest = pdf_module.compute_content_digest(str(original_path))
        record = {
            "doc_id": doc_id,
            "original_filename": uploaded_file.filename,
            "content_hash_hex": content_digest.hex(),
            "signed_hashes": [],
            "created_at": datetime.utcnow().isoformat(),
            "signers": []
        }
        working_path = original_path
    else:
        record = load_signature_record(doc_id)
        original_path = DOCUMENTS_DIR / f"{doc_id}_original.pdf"
        content_digest = bytes.fromhex(record["content_hash_hex"])
        if uploaded_file and uploaded_file.filename:
            temp_check_path = DOCUMENTS_DIR / f"{doc_id}_check_temp.pdf"
            uploaded_file.save(str(temp_check_path))
            new_digest = pdf_module.compute_content_digest(str(temp_check_path))
            temp_check_path.unlink(missing_ok=True)
            if new_digest.hex() not in known_hashes(record):
                flash("Isi dokumen tidak cocok dengan dokumen asli, penandatanganan dibatalkan", "error")
                return redirect(url_for("sign_page"))
        working_path = original_path

    signature = signer_module.sign_digest(private_key, content_digest)
    public_key_pem = key_module.public_key_to_pem(private_key.public_key()).decode("utf-8")

    signer_entry = {
        "signer_id": uuid.uuid4().hex[:8],
        "owner_id": owner_id,
        "signer_name": signer_name,
        "position": position,
        "institution": institution,
        "signed_date": signed_date,
        "algorithm": "RSA-2048-PSS-SHA256",
        "public_key_pem": public_key_pem,
        "signature_b64": base64.b64encode(signature).decode("utf-8")
    }
    record["signers"].append(signer_entry)

    qr_images = []
    for entry in record["signers"]:
        metadata = {
            "doc_id": doc_id,
            "signer_id": entry["signer_id"],
            "name": entry["signer_name"],
            "position": entry["position"],
            "institution": entry["institution"],
            "date": entry["signed_date"],
            "hash": record["content_hash_hex"],
            "verify_url": f"{VERIFY_BASE_URL}?doc_id={doc_id}"
        }
        qr_images.append(qr_module.generate_qr_image(metadata))

    signed_output_path = DOCUMENTS_DIR / f"{doc_id}_signed.pdf"
    pdf_module.embed_qr_images(str(working_path), qr_images, str(signed_output_path))

    signed_hash_hex = pdf_module.compute_content_digest(str(signed_output_path)).hex()
    record.setdefault("signed_hashes", []).append(signed_hash_hex)
    save_signature_record(doc_id, record)

    flash("Dokumen berhasil ditandatangani secara digital", "success")
    return render_template(
        "sign.html",
        key_owners=key_owners,
>>>>>>> e5f9e3f2d4901c926d7e0edf40d3f99ca6aad194
        result=record,
        doc_id=doc_id,
        download_ready=True
    )


@app.route("/download/<doc_id>")
def download_signed(doc_id):
    filename = f"{doc_id}_signed.pdf"
    return send_from_directory(str(DOCUMENTS_DIR), filename, as_attachment=True)


<<<<<<< HEAD
@app.route("/preview/<doc_id>")
def preview_signed(doc_id):
    """Tampilkan PDF bertanda tangan di dalam halaman (iframe) agar semua blok tanda tangan terlihat."""
    response = send_from_directory(
        str(DOCUMENTS_DIR), f"{doc_id}_signed.pdf", mimetype="application/pdf"
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/verify", methods=["GET", "POST"])
def verify_page():
    """Verifikasi MANUAL: pengguna mengunggah PDF sendiri."""
    prefill = request.args.get("doc_id", "").strip()
    if request.method == "GET":
        return render_template("verify.html", prefill_doc_id=prefill)
=======
@app.route("/verify", methods=["GET", "POST"])
def verify_page():
    if request.method == "GET":
        return render_template("verify.html")
>>>>>>> e5f9e3f2d4901c926d7e0edf40d3f99ca6aad194

    uploaded_file = request.files.get("document")
    override_key_file = request.files.get("override_public_key")
    manual_doc_id = request.form.get("doc_id", "").strip()

<<<<<<< HEAD
    def render_results(results):
        return render_template("verify.html", results=results, prefill_doc_id=manual_doc_id)

    if not (uploaded_file and uploaded_file.filename):
        flash("Unggah berkas PDF terlebih dahulu", "error")
        return redirect(url_for("verify_page"))

=======
    if not uploaded_file or uploaded_file.filename == "":
        flash("Berkas PDF wajib diunggah", "error")
        return redirect(url_for("verify_page"))

    temp_path = DOCUMENTS_DIR / f"verify_temp_{uuid.uuid4().hex[:8]}.pdf"
    uploaded_file.save(str(temp_path))

    try:
        images = pdf_module.extract_embedded_images(str(temp_path))
        decoded_list = qr_module.decode_qr_from_images(images)
    except Exception:
        decoded_list = []

    doc_id = manual_doc_id
    if not doc_id and decoded_list:
        doc_id = decoded_list[0].get("doc_id", "")

    if not doc_id:
        results = {"error": "Tidak dapat menemukan doc_id dari QR-Code maupun input manual"}
        temp_path.unlink(missing_ok=True)
        return render_template("verify.html", results=results)

    record = load_signature_record(doc_id)
    if record is None:
        results = {"error": f"Dokumen dengan doc_id {doc_id} tidak ditemukan di penyimpanan"}
        temp_path.unlink(missing_ok=True)
        return render_template("verify.html", results=results)

    try:
        current_digest = pdf_module.compute_content_digest(str(temp_path))
    except Exception:
        current_digest = None

    stored_digest = bytes.fromhex(record["content_hash_hex"])
    integrity_ok = current_digest is not None and current_digest.hex() in known_hashes(record)

>>>>>>> e5f9e3f2d4901c926d7e0edf40d3f99ca6aad194
    override_public_key = None
    if override_key_file and override_key_file.filename:
        try:
            override_public_key = key_module.load_public_key_from_pem(override_key_file.read())
        except Exception:
<<<<<<< HEAD
            return render_results({"error": "Kunci publik tidak valid (harus berkas .pem)"})

    results = verify_pdf_bytes(uploaded_file.read(), manual_doc_id, override_public_key)
    return render_results(results)


# ---------------------------------------------------------------------------
# Data acak untuk tombol "Isi acak"
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Benchmark (waktu dan ukuran) dengan ekspor Excel
# ---------------------------------------------------------------------------

def store_quantitative(report):
    """Simpan hasil dan berkas Excel sekali saja; unduhan hanya mengirim berkas ini."""
    app.config["LAST_QUANT"] = report
    try:
        app.config["LAST_QUANT_XLSX"] = benchmark_module.export_xlsx(report)
        return True
    except ImportError:
        app.config["LAST_QUANT_XLSX"] = None
        return False


@app.route("/benchmark", methods=["GET", "POST"])
def benchmark_page():
    """TAB 4: Uji Kuantitatif dan Benchmark."""
    report = None
    if request.method == "POST":
        try:
            trials = int(request.form.get("trials", benchmark_module.DEFAULT_TRIALS))
        except ValueError:
            trials = benchmark_module.DEFAULT_TRIALS
        trials = min(max(trials, 30), 1000)
        report = benchmark_module.run_full(trials)
        if not store_quantitative(report):
            flash("Paket openpyxl belum terpasang. Jalankan: pip install openpyxl", "error")
    return render_template("benchmark.html", report=report,
                           xlsx_ready=bool(app.config.get("LAST_QUANT_XLSX")) if report else False)


@app.route("/benchmark/xlsx")
def benchmark_xlsx():
    """Unduh rekapitulasi data pengujian (.xlsx, 3 sheet)."""
    if app.config.get("LAST_QUANT") is None:
        store_quantitative(benchmark_module.run_full(benchmark_module.DEFAULT_TRIALS))
    data = app.config.get("LAST_QUANT_XLSX")
    if not data:
        flash("Paket openpyxl belum terpasang. Jalankan: pip install openpyxl", "error")
        return redirect(url_for("benchmark_page"))
    return send_file(
        BytesIO(data), as_attachment=True, download_name="rekap_pengujian_digisign.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/api/random")
def api_random():
    """Data acak untuk mengisi form (tombol 'Isi Data Acak')."""
    if not test_tools_enabled():
        abort(404)
    data = randomdata.random_signer()
    data["owner_id"] = randomdata.random_owner_id()
    data["passphrase"] = randomdata.random_passphrase()
    response = jsonify(data)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/api/random_key", methods=["POST"])
def api_random_key():
    """Buat pasangan kunci dengan nama dan passphrase acak, lalu kembalikan keduanya."""
    if not test_tools_enabled():
        abort(404)
    owner_id = randomdata.random_owner_id()
    while key_module.key_exists(owner_id):
        owner_id = randomdata.random_owner_id()
    passphrase = randomdata.random_passphrase()
    key_module.generate_keypair(owner_id, passphrase)
    response = jsonify({"owner_id": owner_id, "passphrase": passphrase})
    response.headers["Cache-Control"] = "no-store"
    return response
=======
            temp_path.unlink(missing_ok=True)
            results = {"error": "Berkas kunci publik tidak valid (harus berformat PEM)"}
            return render_template("verify.html", results=results)

    signer_results = []
    for entry in record["signers"]:
        public_key = override_public_key if override_public_key else key_module.load_public_key_from_pem(
            entry["public_key_pem"].encode("utf-8")
        )
        signature_bytes = base64.b64decode(entry["signature_b64"])
        if integrity_ok:
            sig_valid = verifier_module.verify_digest(public_key, stored_digest, signature_bytes)
        else:
            sig_valid = False
        signer_results.append({
            "signer_name": entry["signer_name"],
            "position": entry["position"],
            "institution": entry["institution"],
            "signed_date": entry["signed_date"],
            "signature_valid": sig_valid
        })

    results = {
        "doc_id": doc_id,
        "integrity_ok": integrity_ok,
        "signers": signer_results,
        "qr_metadata_found": decoded_list,
        "overall_valid": integrity_ok and len(signer_results) > 0 and all(s["signature_valid"] for s in signer_results)
    }
    temp_path.unlink(missing_ok=True)
    return render_template("verify.html", results=results)
>>>>>>> e5f9e3f2d4901c926d7e0edf40d3f99ca6aad194


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
