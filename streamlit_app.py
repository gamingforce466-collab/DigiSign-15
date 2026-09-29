import hmac
import io
import os
from datetime import date
from urllib.parse import urlsplit

import streamlit as st
from reportlab.pdfgen import canvas

st.set_page_config(page_title="DigiSign", page_icon="✍", layout="wide")


def _setting(name, default=None):
    value = os.environ.get(name)
    if value is not None:
        return value
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


configured_data_dir = _setting("DIGISIGN_DATA_DIR")
if configured_data_dir:
    os.environ["DIGISIGN_DATA_DIR"] = str(configured_data_dir)

import app as flask_app
import document_formats
import randomdata
from crypto import benchmark as benchmark_module
from crypto import excel_exporter, keys as key_module
from services import maintenance as maintenance_service

MAX_SOURCE_DOCUMENT_SIZE = 30 * 1024 * 1024
MAX_REQUEST_SIZE = 64 * 1024 * 1024
ALLOWED_EXTENSIONS = ["pdf", "docx", "jpg", "jpeg", "png", "txt", "xlsx"]
STATUS_INFO = {
    "VALID": "Dokumen utuh dan semua tanda tangan cocok.",
    "TAMPERED": "Isi dokumen berbeda dari yang ditandatangani. Ditolak.",
    "KEY_MISMATCH": "Dokumen utuh, tetapi kunci publik tidak cocok dengan tanda tangan. Ditolak.",
    "QR_FORGED": "QR-Code tidak terdaftar atau datanya tidak cocok. Ditolak.",
    "NOT_FOUND": "Doc ID tidak ditemukan. Ditolak.",
    "NO_QR": "QR-Code tidak terbaca dan Doc ID tidak diisi.",
}

def _public_app_url():
    configured_url = _setting("STREAMLIT_VERIFY_BASE_URL")
    if configured_url:
        return str(configured_url).rstrip("/")
    try:
        current_url = st.context.url
    except Exception:
        current_url = ""
    parsed_url = urlsplit(current_url)
    if parsed_url.scheme in {"http", "https"} and parsed_url.netloc:
        return f"{parsed_url.scheme}://{parsed_url.netloc}"
    return "http://localhost:8501"


flask_app.VERIFY_BASE_URL = _public_app_url()
ACCESS_PASSWORD = str(_setting("STREAMLIT_ACCESS_PASSWORD", "")).strip()


def _require_access():
    if len(ACCESS_PASSWORD) < 8:
        st.title("DigiSign")
        st.error("Aplikasi terkunci. Atur STREAMLIT_ACCESS_PASSWORD minimal 8 karakter di Secrets.")
        st.stop()

    if st.session_state.get("authenticated"):
        return

    st.title("DigiSign")
    with st.form("access_form"):
        password = st.text_input("Password akses", type="password")
        submitted = st.form_submit_button("Masuk", type="primary")
    if submitted:
        if hmac.compare_digest(password.encode("utf-8"), ACCESS_PASSWORD.encode("utf-8")):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Password akses salah.")
    st.stop()


def _render_home():
    records = flask_app.list_signature_records()
    key_owners = key_module.list_keys()
    total_signers = sum(len(record.get("signers", [])) for record in records)

    st.title("DigiSign")
    st.caption("Tanda tangan digital RSA-2048-PSS dan verifikasi dokumen.")
    metrics = st.columns(3)
    metrics[0].metric("Dokumen", len(records))
    metrics[1].metric("Tanda tangan", total_signers)
    metrics[2].metric("Pasangan kunci", len(key_owners))

    st.subheader("Dokumen")
    if not records:
        st.info("Belum ada dokumen bertanda tangan.")
    for record in records:
        doc_id = record["doc_id"]
        extension = flask_app.record_file_extension(record)
        signed_path = flask_app.DOCUMENTS_DIR / f"{doc_id}_signed{extension}"
        original_path = flask_app.DOCUMENTS_DIR / f"{doc_id}_original{extension}"
        with st.container(border=True):
            details, signed_download, original_download, add_signer = st.columns([5, 1, 1, 1])
            with details:
                st.markdown(f"**{record.get('original_filename', 'Dokumen')}**")
                st.caption(
                    f"Doc ID: `{doc_id}` · {len(record.get('signers', []))} penandatangan · "
                    f"{record.get('created_at', '')[:16].replace('T', ' ')}"
                )
            with signed_download:
                if signed_path.is_file():
                    st.download_button(
                        "Bertanda tangan",
                        data=signed_path.read_bytes(),
                        file_name=f"{doc_id}_signed{extension}",
                        mime=document_formats.MIME_TYPES[extension],
                        key=f"download_home_{doc_id}",
                        use_container_width=True,
                    )
            with original_download:
                if original_path.is_file():
                    st.download_button(
                        "Dokumen asli",
                        data=original_path.read_bytes(),
                        file_name=f"{doc_id}_original{extension}",
                        mime=document_formats.MIME_TYPES[extension],
                        key=f"download_original_home_{doc_id}",
                        use_container_width=True,
                    )
            with add_signer:
                st.button(
                    "Tambah TTD",
                    key=f"add_signer_{doc_id}",
                    on_click=_open_signing_page,
                    args=(doc_id,),
                    use_container_width=True,
                )

    st.subheader("Kunci")
    if key_owners:
        st.caption("Private key diunduh dalam keadaan terenkripsi; passphrase tidak dapat dipulihkan.")
        for owner in key_owners:
            public_path = key_module.KEYS_DIR / f"{owner}_public.pem"
            private_path = key_module.KEYS_DIR / f"{owner}_private.pem"
            name, public_download, private_download = st.columns([4, 1, 1])
            name.write(f"`{owner}`")
            if public_path.is_file():
                public_download.download_button(
                    "Kunci publik",
                    data=public_path.read_bytes(),
                    file_name=public_path.name,
                    mime="application/x-pem-file",
                    key=f"download_public_key_home_{owner}",
                )
            if private_path.is_file():
                private_download.download_button(
                    "Private key terenkripsi",
                    data=private_path.read_bytes(),
                    file_name=private_path.name,
                    mime="application/x-pem-file",
                    key=f"download_private_key_home_{owner}",
                )
    else:
        st.info("Belum ada pasangan kunci.")

    st.divider()
    st.subheader("Bersihkan penyimpanan")
    st.warning("Tindakan ini menghapus semua kunci, dokumen, dan data tanda tangan.")
    confirmed = st.checkbox("Saya memahami bahwa data yang dihapus tidak dapat dipulihkan.")
    if st.button("Bersihkan semua data", type="secondary", disabled=not confirmed):
        counts = maintenance_service.clear_storage(
            flask_app.DOCUMENTS_DIR, flask_app.SIGNATURES_DIR, key_module.KEYS_DIR
        )
        st.success(
            f"Dihapus: {counts['documents']} berkas, {counts['signatures']} tanda tangan, "
            f"{counts['keys']} kunci."
        )
        st.rerun()


def _open_signing_page(doc_id):
    st.session_state["sign_doc_id"] = doc_id
    st.session_state["page"] = "Tanda Tangan"


def _render_key_creation():
    st.subheader("Buat pasangan kunci")
    created_owner = st.session_state.pop("created_key_owner", None)
    if created_owner:
        st.session_state["signing_owner_id"] = created_owner
        st.success(f"Pasangan kunci RSA-2048 untuk `{created_owner}` berhasil dibuat.")
    if st.button("Isi data kunci acak", key="random_key_data"):
        st.session_state["new_key_owner"] = randomdata.random_owner_id()
        st.session_state["new_key_passphrase"] = randomdata.random_passphrase()

    with st.form("create_key_form"):
        owner_id = st.text_input("Nama kunci", key="new_key_owner", max_chars=40)
        passphrase = st.text_input("Passphrase", type="password", key="new_key_passphrase")
        submitted = st.form_submit_button("Buat kunci")

    if submitted:
        if not owner_id or not passphrase:
            st.error("Nama kunci dan passphrase wajib diisi.")
        elif not flask_app.OWNER_PATTERN.fullmatch(owner_id):
            st.error("Nama kunci hanya boleh berisi huruf, angka, _ dan - (maksimal 40 karakter).")
        elif key_module.key_exists(owner_id):
            st.error("Nama kunci sudah dipakai.")
        else:
            try:
                key_module.generate_keypair(owner_id, passphrase)
            except Exception as exc:
                st.error(f"Kunci gagal dibuat: {exc}")
            else:
                st.session_state["created_key_owner"] = owner_id
                st.rerun()


def _render_signing():
    records = flask_app.list_signature_records()
    key_owners = key_module.list_keys()
    st.title("Tanda Tangan")
    _render_key_creation()
    st.divider()
    st.subheader("Tandatangani dokumen")

    if st.button("Isi data penandatangan acak"):
        values = randomdata.random_signer()
        st.session_state["signer_name"] = values["signer_name"]
        st.session_state["signer_position"] = values["position"]
        st.session_state["signer_institution"] = values["institution"]
        st.session_state["signer_date"] = date.fromisoformat(values["signed_date"])

    owner_id = st.text_input(
        "Kunci penandatangan",
        key="signing_owner_id",
        placeholder="Ketik nama kunci",
    ).strip()
    if key_owners:
        st.caption("Kunci tersedia: " + ", ".join(key_owners))
    else:
        st.caption("Belum ada kunci. Buat pasangan kunci terlebih dahulu.")

    record_by_id = {record["doc_id"]: record for record in records}
    selected_doc_id = st.session_state.get("sign_doc_id", "")
    if selected_doc_id and selected_doc_id not in record_by_id:
        st.session_state["sign_doc_id"] = ""
    options = [""] + list(record_by_id)
    label_by_id = {
        "": "Dokumen baru (unggah berkas)",
        **{
            doc_id: (
                f"Tambah TTD: {doc_id} ({record.get('original_filename', 'dokumen')}, "
                f"{len(record.get('signers', []))} TTD)"
            )
            for doc_id, record in record_by_id.items()
        },
    }

    with st.form("sign_document_form"):
        doc_id = st.selectbox(
            "Dokumen",
            options,
            format_func=lambda value: label_by_id[value],
            key="sign_doc_id",
        )
        passphrase = st.text_input("Passphrase kunci", type="password", key="signing_passphrase")
        signer_name = st.text_input("Nama penandatangan", key="signer_name")
        position = st.text_input("Jabatan", key="signer_position")
        institution = st.text_input("Institusi", key="signer_institution")
        signed_date = st.date_input("Tanggal tanda tangan", key="signer_date")
        uploaded = st.file_uploader(
            "Dokumen (PDF, DOCX, JPG/JPEG, PNG, TXT, XLSX)",
            type=ALLOWED_EXTENSIONS,
            help="Berkas sumber maksimal 30 MiB. Saat menambah penandatangan, unggah ulang bersifat opsional.",
        )
        submitted = st.form_submit_button("Tandatangani", type="primary")

    if submitted:
        data = uploaded.getvalue() if uploaded else None
        if not owner_id:
            st.error("Isi nama kunci penandatangan.")
        elif owner_id not in key_owners:
            st.error("Kunci tidak ditemukan. Periksa nama kunci yang tersedia di Beranda.")
        elif data and len(data) > MAX_SOURCE_DOCUMENT_SIZE and not doc_id:
            st.error("Ukuran berkas sumber maksimal 30 MiB.")
        elif data and len(data) > MAX_REQUEST_SIZE:
            st.error("Ukuran berkas maksimal 64 MiB.")
        else:
            try:
                new_doc_id, record = flask_app.perform_signing(
                    owner_id,
                    passphrase,
                    signer_name.strip(),
                    position.strip(),
                    institution.strip(),
                    signed_date.isoformat(),
                    doc_id=doc_id,
                    pdf_bytes=data,
                    original_filename=uploaded.name if uploaded else None,
                )
            except (flask_app.SigningError, ValueError) as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Penandatanganan gagal: {exc}")
            else:
                st.session_state["last_signed_doc_id"] = new_doc_id
                st.success(f"Dokumen `{new_doc_id}` berhasil ditandatangani.")
                st.rerun()

    result_doc_id = st.session_state.get("last_signed_doc_id")
    if result_doc_id:
        record = flask_app.load_signature_record(result_doc_id)
        if record:
            st.subheader("Hasil terakhir")
            st.caption(f"Doc ID: `{result_doc_id}` · {len(record['signers'])} tanda tangan")
            st.dataframe(
                [
                    {
                        "Nama": signer["signer_name"],
                        "Jabatan": signer["position"],
                        "Institusi": signer["institution"],
                        "Tanggal": signer["signed_date"],
                        "Kunci": signer["owner_id"],
                    }
                    for signer in record["signers"]
                ],
                hide_index=True,
                use_container_width=True,
            )
            extension = flask_app.record_file_extension(record)
            signed_path = flask_app.DOCUMENTS_DIR / f"{result_doc_id}_signed{extension}"
            if signed_path.is_file():
                st.download_button(
                    "Unduh dokumen bertanda tangan",
                    data=signed_path.read_bytes(),
                    file_name=signed_path.name,
                    mime=document_formats.MIME_TYPES[extension],
                    key=f"download_result_{result_doc_id}",
                )


def _show_verification_result(results):
    status = results.get("status", "ERROR")
    if status == "VALID":
        st.success(f"{status}: {STATUS_INFO[status]}")
    else:
        st.error(f"{status}: {STATUS_INFO.get(status, 'Verifikasi gagal.')}")
    if results.get("error"):
        st.warning(results["error"])
        return

    st.write(f"Doc ID: `{results.get('doc_id', '')}`")
    if results.get("original_filename"):
        st.caption(results["original_filename"])
    columns = st.columns(3)
    columns[0].metric("Integritas", "Utuh" if results.get("integrity_ok") else "Berubah")
    columns[1].metric("QR/metadata ditemukan", results.get("signers_in_document", 0))
    columns[2].metric("Total penandatangan", results.get("signers_total", 0))
    if results.get("integrity_ok") and results.get("signers_in_document", 0) < results.get("signers_total", 0):
        st.info("Ini versi dokumen yang lebih lama; sebagian tanda tangan berikutnya belum tercantum.")
    st.dataframe(
        [
            {
                "#": signer["number"],
                "Nama": signer["signer_name"],
                "Jabatan": signer["position"],
                "Institusi": signer["institution"],
                "Tanggal": signer["signed_date"],
                "QR/metadata": {
                    "ok": "Cocok",
                    "mismatch": "Tidak cocok",
                    "missing": "Tidak ada",
                }.get(signer["qr_status"], signer["qr_status"]),
                "Tanda tangan": "Valid" if signer["signature_valid"] else "Tidak valid",
            }
            for signer in results.get("signers", [])
        ],
        hide_index=True,
        use_container_width=True,
    )


def _render_verification():
    st.title("Verifikasi")
    st.caption("Unggah dokumen bertanda tangan untuk memeriksa integritas, QR-Code, dan tanda tangan.")
    query_doc_id = st.query_params.get("doc_id", "")
    if "verify_doc_id" not in st.session_state:
        st.session_state["verify_doc_id"] = query_doc_id

    with st.form("verify_document_form"):
        uploaded = st.file_uploader(
            "Dokumen (PDF, DOCX, JPG/JPEG, PNG, TXT, XLSX)",
            type=ALLOWED_EXTENSIONS,
            help="Hasil bertanda tangan dapat berukuran hingga 64 MiB.",
        )
        manual_doc_id = st.text_input("Doc ID (opsional)", key="verify_doc_id")
        public_key_file = st.file_uploader("Kunci publik pembanding (.pem, opsional)", type=["pem"])
        submitted = st.form_submit_button("Verifikasi", type="primary")

    if submitted:
        if not uploaded:
            st.error("Pilih dokumen yang akan diverifikasi.")
        elif len(uploaded.getvalue()) > MAX_REQUEST_SIZE:
            st.error("Ukuran dokumen maksimal 64 MiB.")
        elif not document_formats.is_valid_document(uploaded.getvalue(), uploaded.name):
            st.error("Format tidak didukung atau berkas tidak valid.")
        else:
            override_public_key = None
            if public_key_file:
                try:
                    override_public_key = key_module.load_public_key_from_pem(public_key_file.getvalue())
                except Exception:
                    st.error("Kunci publik tidak valid; gunakan berkas .pem.")
                    return
            try:
                results = flask_app.verify_pdf_bytes(
                    uploaded.getvalue(),
                    manual_doc_id.strip(),
                    override_public_key,
                    uploaded.name,
                )
            except Exception as exc:
                st.error(f"Verifikasi gagal: {exc}")
            else:
                st.session_state["last_verification"] = results

    results = st.session_state.get("last_verification")
    if results:
        st.subheader("Hasil verifikasi")
        _show_verification_result(results)


def _render_demo():
    st.title("Demo end-to-end")
    st.caption("Riwayat, dokumen, dan key demo dimuat dari penyimpanan server, bukan dari sesi browser.")
    st.info("Key demo `demo_digisign` dapat dipakai untuk tanda tangan manual. Passphrase-nya sama dengan password akses aplikasi.")

    if st.button("Jalankan demo lengkap", type="primary", key="run_end_to_end_demo"):
        owner_id = "demo_digisign"
        passphrase = ACCESS_PASSWORD
        try:
            with st.spinner("Membuat kunci dan menjalankan pengujian..."):
                if not key_module.key_exists(owner_id):
                    key_module.generate_keypair(owner_id, passphrase)
                else:
                    try:
                        key_module.load_private_key(owner_id, passphrase)
                    except Exception:
                        key_module.delete_keypair(owner_id)
                        key_module.generate_keypair(owner_id, passphrase)
                source = io.BytesIO()
                sample_pdf = canvas.Canvas(source)
                sample_pdf.drawString(72, 720, "Dokumen contoh DigiSign untuk demo end-to-end")
                sample_pdf.save()

                doc_id, record = flask_app.perform_signing(
                    owner_id,
                    passphrase,
                    "Penandatangan Demo",
                    "Penguji",
                    "DigiSign",
                    date.today().isoformat(),
                    pdf_bytes=source.getvalue(),
                    original_filename="dokumen_demo.pdf",
                )
                signed_path = flask_app.DOCUMENTS_DIR / f"{doc_id}_signed.pdf"
                signed_bytes = signed_path.read_bytes()
                valid_result = flask_app.verify_pdf_bytes(
                    signed_bytes, original_filename=signed_path.name
                )
                tampered_result = flask_app.verify_pdf_bytes(
                    flask_app.flip_one_byte(signed_bytes),
                    doc_id,
                    original_filename=signed_path.name,
                )
                record["demo_results"] = {
                    "valid": valid_result.get("status"),
                    "tampered": tampered_result.get("status"),
                }
                flask_app.save_signature_record(doc_id, record)
                st.success(f"Demo selesai. Doc ID `{doc_id}` tersimpan di server.")
        except Exception as exc:
            st.error(f"Demo gagal dijalankan: {exc}")

    demo_records = [
        record for record in flask_app.list_signature_records()
        if any(signer.get("owner_id", "").startswith("demo_") for signer in record.get("signers", []))
    ]
    st.subheader("Riwayat demo tersimpan")
    if not demo_records:
        st.info("Belum ada data demo. Jalankan demo untuk membuat key dan dokumen pertama.")
    for record in demo_records:
        doc_id = record["doc_id"]
        extension = flask_app.record_file_extension(record)
        original_path = flask_app.DOCUMENTS_DIR / f"{doc_id}_original{extension}"
        signed_path = flask_app.DOCUMENTS_DIR / f"{doc_id}_signed{extension}"
        owner_ids = sorted({signer.get("owner_id", "") for signer in record.get("signers", [])})
        with st.container(border=True):
            st.markdown(f"**{record.get('original_filename', 'Dokumen demo')}**")
            st.caption(f"Doc ID: `{doc_id}` · {record.get('created_at', '')[:16].replace('T', ' ')}")
            results = record.get("demo_results", {})
            if results:
                status_columns = st.columns(2)
                status_columns[0].metric("Dokumen asli", results.get("valid", "-"))
                status_columns[1].metric("Dokumen diubah", results.get("tampered", "-"))
            downloads = st.columns(4)
            if original_path.is_file():
                downloads[0].download_button(
                    "Dokumen asli",
                    data=original_path.read_bytes(),
                    file_name=original_path.name,
                    mime=document_formats.MIME_TYPES[extension],
                    key=f"download_demo_original_{doc_id}",
                )
            if signed_path.is_file():
                downloads[1].download_button(
                    "Bertanda tangan",
                    data=signed_path.read_bytes(),
                    file_name=signed_path.name,
                    mime=document_formats.MIME_TYPES[extension],
                    key=f"download_demo_signed_{doc_id}",
                )
            for index, owner_id in enumerate(owner_ids):
                public_path = key_module.KEYS_DIR / f"{owner_id}_public.pem"
                private_path = key_module.KEYS_DIR / f"{owner_id}_private.pem"
                if public_path.is_file():
                    downloads[2].download_button(
                        f"Public key {owner_id}",
                        data=public_path.read_bytes(),
                        file_name=public_path.name,
                        mime="application/x-pem-file",
                        key=f"download_demo_public_{doc_id}_{index}",
                    )
                if private_path.is_file():
                    downloads[3].download_button(
                        f"Private key terenkripsi {owner_id}",
                        data=private_path.read_bytes(),
                        file_name=private_path.name,
                        mime="application/x-pem-file",
                        key=f"download_demo_private_{doc_id}_{index}",
                    )


def _render_benchmark():
    st.title("Uji Kuantitatif")
    st.caption("Benchmark tanda tangan/verifikasi, ukuran kunci, dan uji tamper satu byte.")
    with st.form("benchmark_form"):
        trials = st.number_input("Jumlah percobaan per algoritma", min_value=30, max_value=1000, value=30, step=10)
        submitted = st.form_submit_button("Jalankan pengujian", type="primary")

    if submitted:
        try:
            with st.spinner("Benchmark dan uji tamper sedang berjalan..."):
                st.session_state["benchmark_report"] = benchmark_module.run_full(int(trials))
        except Exception as exc:
            st.error(f"Pengujian gagal: {exc}")

    report = st.session_state.get("benchmark_report")
    if not report:
        return

    st.subheader(f"Hasil {report['trials']} percobaan")
    benchmark_rows = []
    for algorithm in report["algorithms"]:
        benchmark_rows.append(
            {
                "Algoritma": algorithm["name"],
                "Tanda tangan mean (ms)": round(algorithm["sign"]["mean"], 4),
                "Verifikasi mean (ms)": round(algorithm["verify"]["mean"], 4),
                "Tanda tangan (byte)": algorithm["sizes"]["signature_bytes"],
                "Kunci publik PEM (byte)": algorithm["sizes"]["public_key_pem_bytes"],
            }
        )
    st.dataframe(benchmark_rows, hide_index=True, use_container_width=True)
    tamper = report["tamper"]
    st.metric("Uji tamper", f"{'LULUS' if tamper['all_passed'] else 'GAGAL'} · {sum(row['passed'] for row in tamper['rows'])}/10")
    st.dataframe(
        [
            {
                "No": row["number"],
                "Posisi (%)": row["position_pct"],
                "Status": row["status"],
                "Hasil": "LULUS" if row["passed"] else "GAGAL",
            }
            for row in tamper["rows"]
        ],
        hide_index=True,
        use_container_width=True,
    )
    st.download_button(
        "Unduh rekapitulasi Excel",
        data=excel_exporter.export_xlsx(report),
        file_name="rekap_pengujian_digisign.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


_require_access()

if st.query_params.get("doc_id") and "page" not in st.session_state:
    st.session_state["page"] = "Verifikasi"

st.sidebar.title("DigiSign")
page = st.sidebar.radio(
    "Menu",
    ["Beranda", "Tanda Tangan", "Verifikasi", "Demo End-to-End", "Uji Kuantitatif"],
    key="page",
)
if st.sidebar.button("Keluar"):
    st.session_state["authenticated"] = False
    st.rerun()
if page == "Beranda":
    _render_home()
elif page == "Tanda Tangan":
    _render_signing()
elif page == "Verifikasi":
    _render_verification()
elif page == "Demo End-to-End":
    _render_demo()
else:
    _render_benchmark()