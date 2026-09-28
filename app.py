import os
import json
import uuid
import base64
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from dotenv import load_dotenv

from crypto import keys as key_module
from crypto import signer as signer_module
from crypto import verifier as verifier_module
from pdf import handler as pdf_module
from qr import generator as qr_module

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


def signature_record_path(doc_id):
    return SIGNATURES_DIR / f"{doc_id}.json"


def load_signature_record(doc_id):
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
    return records


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


@app.route("/generate_keys", methods=["POST"])
def generate_keys():
    owner_id = request.form.get("owner_id", "").strip()
    passphrase = request.form.get("passphrase", "")
    if not owner_id or not passphrase:
        flash("Nama pemilik kunci dan passphrase wajib diisi", "error")
        return redirect(url_for("sign_page"))
    if key_module.key_exists(owner_id):
        flash("Kunci dengan nama tersebut sudah ada", "error")
        return redirect(url_for("sign_page"))
    key_module.generate_keypair(owner_id, passphrase)
    flash(f"Pasangan kunci RSA 2048-bit untuk {owner_id} berhasil dibuat", "success")
    return redirect(url_for("sign_page"))


@app.route("/sign", methods=["GET", "POST"])
def sign_page():
    key_owners = key_module.list_keys()
    if request.method == "GET":
        return render_template("sign.html", key_owners=key_owners)

    doc_id = request.form.get("doc_id", "").strip()
    owner_id = request.form.get("owner_id", "").strip()
    passphrase = request.form.get("passphrase", "")
    signer_name = request.form.get("signer_name", "").strip()
    position = request.form.get("position", "").strip()
    institution = request.form.get("institution", "").strip()
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
        result=record,
        doc_id=doc_id,
        download_ready=True
    )


@app.route("/download/<doc_id>")
def download_signed(doc_id):
    filename = f"{doc_id}_signed.pdf"
    return send_from_directory(str(DOCUMENTS_DIR), filename, as_attachment=True)


@app.route("/verify", methods=["GET", "POST"])
def verify_page():
    if request.method == "GET":
        return render_template("verify.html")

    uploaded_file = request.files.get("document")
    override_key_file = request.files.get("override_public_key")
    manual_doc_id = request.form.get("doc_id", "").strip()

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

    override_public_key = None
    if override_key_file and override_key_file.filename:
        try:
            override_public_key = key_module.load_public_key_from_pem(override_key_file.read())
        except Exception:
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


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
