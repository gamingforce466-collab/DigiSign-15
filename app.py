import os
import re
from io import BytesIO
from pathlib import Path
from datetime import datetime, timezone
from flask import (
    Flask, render_template, request, redirect, url_for,
    send_from_directory, send_file, flash, jsonify, abort
)
from dotenv import load_dotenv

from crypto import keys as key_module
from crypto import signer as signer_module
from crypto import verifier as verifier_module
from crypto import benchmark as benchmark_module
from crypto import excel_exporter as excel_module
from pdf import handler as pdf_module
from qr import generator as qr_module
import document_formats as document_module
import randomdata
from services.document_workflow import DocumentWorkflow, SigningError
from services import maintenance as maintenance_service
from services import scenarios as scenario_service

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DOCUMENTS_DIR = BASE_DIR / "storage" / "documents"
SIGNATURES_DIR = BASE_DIR / "storage" / "signatures"
KEYS_DIR = BASE_DIR / "storage" / "keys"
for d in (DOCUMENTS_DIR, SIGNATURES_DIR, KEYS_DIR):
    d.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_fallback_secret_key")
MAX_SOURCE_DOCUMENT_SIZE = 30 * 1024 * 1024
MAX_REQUEST_SIZE = 64 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_SIZE

VERIFY_BASE_URL = os.environ.get("VERIFY_BASE_URL", "http://localhost:5000/verify")

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


def _document_workflow():
    return DocumentWorkflow(
        documents_dir=DOCUMENTS_DIR,
        signatures_dir=SIGNATURES_DIR,
        key_module=key_module,
        signer_module=signer_module,
        verifier_module=verifier_module,
        document_module=document_module,
        qr_module=qr_module,
        owner_pattern=OWNER_PATTERN,
        doc_id_pattern=DOC_ID_PATTERN,
        verify_base_url=VERIFY_BASE_URL,
        utc_now=utc_now,
    )


def valid_doc_id(doc_id):
    return _document_workflow().valid_doc_id(doc_id)


def signature_record_path(doc_id):
    return _document_workflow().signature_record_path(doc_id)


def load_signature_record(doc_id):
    return _document_workflow().load_signature_record(doc_id)


def save_signature_record(doc_id, record):
    return _document_workflow().save_signature_record(doc_id, record)


def known_hashes(record):
    return _document_workflow().known_hashes(record)


def record_file_extension(record):
    return _document_workflow().record_file_extension(record)


def list_signature_records():
    return _document_workflow().list_signature_records()


def perform_signing(*args, **kwargs):
    return _document_workflow().perform_signing(*args, **kwargs)


# ---------------------------------------------------------------------------
# Verifikasi (dipakai oleh halaman /verify dan uji otomatis)
# ---------------------------------------------------------------------------

def decide_status(integrity_ok, signers, qr_forged):
    return _document_workflow().decide_status(integrity_ok, signers, qr_forged)


def compute_verification(pdf_path, manual_doc_id="", override_public_key=None, file_extension=None):
    return _document_workflow().compute_verification(
        pdf_path, manual_doc_id, override_public_key, file_extension
    )


def verify_pdf_bytes(data, manual_doc_id="", override_public_key=None, original_filename=""):
    return _document_workflow().verify_bytes(data, manual_doc_id, override_public_key, original_filename)


def flip_one_byte(data):
    return scenario_service.flip_one_byte(data)


def make_fake_qr_pdf():
    return scenario_service.make_fake_qr_pdf(
        DOCUMENTS_DIR, VERIFY_BASE_URL, utc_now, randomdata, qr_module, pdf_module
    )


def paste_real_qr_on_other_pdf(signed_pdf_bytes):
    return scenario_service.paste_real_qr_on_other_pdf(
        signed_pdf_bytes, DOCUMENTS_DIR, randomdata, pdf_module
    )


# ---------------------------------------------------------------------------
# Halaman utama
# ---------------------------------------------------------------------------

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


def clear_storage():
    return maintenance_service.clear_storage(DOCUMENTS_DIR, SIGNATURES_DIR, key_module.KEYS_DIR)


@app.route("/clear", methods=["POST"])
def clear_all():
    counts = clear_storage()
    flash(f"Data dibersihkan: {counts['documents']} PDF, {counts['signatures']} data tanda tangan, "
          f"{counts['keys']} berkas kunci", "success")
    return redirect(url_for("index"))


@app.route("/generate_keys", methods=["POST"])
def generate_keys():
    owner_id = request.form.get("owner_id", "").strip()
    passphrase = request.form.get("passphrase", "")
    if not owner_id or not passphrase:
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
    return redirect(url_for("sign_page"))


@app.route("/sign", methods=["GET", "POST"])
def sign_page():
    key_owners = key_module.list_keys()
    if request.method == "GET":
        return render_template(
            "sign.html",
            key_owners=key_owners,
            records=list_signature_records(),
            prefill_doc_id=request.args.get("doc_id", "").strip()
        )

    doc_id = request.form.get("doc_id", "").strip()
    owner_id = request.form.get("owner_id", "").strip()
    passphrase = request.form.get("passphrase", "")
    signer_name = request.form.get("signer_name", "").strip()
    position = request.form.get("position", "").strip()
    institution = request.form.get("institution", "").strip()
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
        result=record,
        doc_id=doc_id,
        download_ready=True
    )


@app.errorhandler(413)
def upload_too_large(_error):
    flash("Request terlalu besar. Berkas sumber maksimal 30 MiB; hasil signed untuk verifikasi dapat mencapai 64 MiB.", "error")
    endpoint = "verify_page" if request.path == url_for("verify_page") else "sign_page"
    return redirect(url_for(endpoint))


@app.route("/download/<doc_id>")
def download_signed(doc_id):
    record = load_signature_record(doc_id)
    if record is None:
        abort(404)
    extension = record_file_extension(record)
    filename = f"{doc_id}_signed{extension}"
    return send_from_directory(
        str(DOCUMENTS_DIR), filename, as_attachment=True,
        download_name=filename, mimetype=document_module.MIME_TYPES[extension]
    )


@app.route("/preview/<doc_id>")
def preview_signed(doc_id):
    """Tampilkan PDF bertanda tangan di dalam halaman (iframe) agar semua blok tanda tangan terlihat."""
    record = load_signature_record(doc_id)
    if record is None or record_file_extension(record) != ".pdf":
        abort(404)
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

    uploaded_file = request.files.get("document")
    override_key_file = request.files.get("override_public_key")
    manual_doc_id = request.form.get("doc_id", "").strip()

    def render_results(results):
        return render_template("verify.html", results=results, prefill_doc_id=manual_doc_id)

    if not (uploaded_file and uploaded_file.filename):
        flash("Pilih berkas untuk diverifikasi", "error")
        return redirect(url_for("verify_page"))

    document_bytes = uploaded_file.read()
    if not document_module.is_valid_document(document_bytes, uploaded_file.filename):
        flash("Format tidak didukung atau berkas tidak valid. Gunakan PDF, DOCX, JPG, JPEG, PNG, TXT, atau XLSX", "error")
        return redirect(url_for("verify_page"))

    override_public_key = None
    if override_key_file and override_key_file.filename:
        try:
            override_public_key = key_module.load_public_key_from_pem(override_key_file.read())
        except Exception:
            return render_results({"error": "Kunci publik tidak valid (harus berkas .pem)"})

    results = verify_pdf_bytes(document_bytes, manual_doc_id, override_public_key, uploaded_file.filename)
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
        app.config["LAST_QUANT_XLSX"] = excel_module.export_xlsx(report)
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


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
