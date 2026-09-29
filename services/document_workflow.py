"""Alur bisnis dokumen: record, penandatanganan, dan verifikasi."""
import base64
import json
import uuid
from pathlib import Path


class SigningError(Exception):
    """Kesalahan input atau pemrosesan saat menandatangani dokumen."""


class DocumentWorkflow:
    def __init__(self, documents_dir, signatures_dir, key_module, signer_module,
                 verifier_module, document_module, qr_module, owner_pattern,
                 doc_id_pattern, verify_base_url, utc_now):
        self.documents_dir = Path(documents_dir)
        self.signatures_dir = Path(signatures_dir)
        self.key_module = key_module
        self.signer_module = signer_module
        self.verifier_module = verifier_module
        self.document_module = document_module
        self.qr_module = qr_module
        self.owner_pattern = owner_pattern
        self.doc_id_pattern = doc_id_pattern
        self.verify_base_url = verify_base_url
        self.utc_now = utc_now

    def valid_doc_id(self, doc_id):
        return bool(doc_id and self.doc_id_pattern.match(doc_id))

    def signature_record_path(self, doc_id):
        return self.signatures_dir / f"{doc_id}.json"

    def load_signature_record(self, doc_id):
        if not self.valid_doc_id(doc_id):
            return None
        path = self.signature_record_path(doc_id)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as source:
            return json.load(source)

    def save_signature_record(self, doc_id, record):
        path = self.signature_record_path(doc_id)
        with open(path, "w", encoding="utf-8") as destination:
            json.dump(record, destination, indent=2)

    @staticmethod
    def known_hashes(record):
        return {record["content_hash_hex"], *record.get("signed_hashes", [])}

    def record_file_extension(self, record):
        extension = record.get("file_extension")
        if extension not in self.document_module.MIME_TYPES:
            extension = self.document_module.extension_for(record.get("original_filename"), ".pdf")
        return extension or ".pdf"

    def list_signature_records(self):
        records = []
        for path in sorted(self.signatures_dir.glob("*.json")):
            with open(path, "r", encoding="utf-8") as source:
                record = json.load(source)
            record["file_extension"] = self.record_file_extension(record)
            records.append(record)
        records.sort(key=lambda record: record.get("created_at", ""), reverse=True)
        return records

    def perform_signing(self, owner_id, passphrase, signer_name, position="", institution="",
                        signed_date=None, doc_id="", pdf_bytes=None, original_filename=None):
        if not owner_id or not passphrase or not signer_name:
            raise SigningError("Kunci, passphrase, dan nama penandatangan wajib diisi")
        if not self.owner_pattern.match(owner_id):
            raise SigningError("Nama kunci tidak valid")
        try:
            private_key = self.key_module.load_private_key(owner_id, passphrase)
        except Exception as exc:
            raise SigningError("Passphrase salah atau kunci tidak ditemukan") from exc

        signed_date = signed_date or self.utc_now().strftime("%Y-%m-%d")
        is_new_document = not bool(doc_id)
        if doc_id:
            record = self.load_signature_record(doc_id)
            if record is None:
                raise SigningError(f"Doc ID {doc_id} tidak ditemukan. Pilih dokumen dari daftar")
            extension = self.record_file_extension(record)
            original_path = self.documents_dir / f"{doc_id}_original{extension}"
            if not original_path.exists():
                raise SigningError("Berkas asli dokumen tidak ada di server")
            content_digest = bytes.fromhex(record["content_hash_hex"])
            if pdf_bytes:
                if len(pdf_bytes) > 64 * 1024 * 1024:
                    raise SigningError("Berkas bertanda tangan melebihi batas upload 64 MiB")
                uploaded_extension = self.document_module.extension_for(original_filename, extension)
                if (uploaded_extension != extension
                        or not self.document_module.is_valid_document(pdf_bytes, original_filename)):
                    raise SigningError("Format berkas tambahan harus sama dengan format dokumen dan berkas harus valid")
                temp_check_path = self.documents_dir / f"{doc_id}_check_{uuid.uuid4().hex[:8]}{extension}"
                temp_check_path.write_bytes(pdf_bytes)
                try:
                    new_digest = self.document_module.compute_file_digest(temp_check_path)
                finally:
                    temp_check_path.unlink(missing_ok=True)
                if new_digest.hex() not in self.known_hashes(record):
                    raise SigningError("Isi dokumen tidak cocok dengan berkas yang terdaftar. Penandatanganan dibatalkan")
        else:
            if not pdf_bytes:
                raise SigningError("Pilih berkas yang akan ditandatangani")
            if len(pdf_bytes) > 30 * 1024 * 1024:
                raise SigningError("Ukuran berkas sumber maksimal 30 MiB")
            extension = self.document_module.extension_for(original_filename, ".pdf")
            valid_document = (extension is not None and self.document_module.is_valid_document(
                pdf_bytes, original_filename or f"dokumen{extension}"))
            if not valid_document and extension == ".pdf":
                raise SigningError("Berkas bukan PDF yang valid")
            if not valid_document:
                raise SigningError("Format tidak didukung atau berkas tidak valid. Gunakan PDF, DOCX, JPG, JPEG, PNG, TXT, atau XLSX")
            doc_id = uuid.uuid4().hex[:12]
            original_path = self.documents_dir / f"{doc_id}_original{extension}"
            original_path.write_bytes(pdf_bytes)
            content_digest = self.document_module.compute_file_digest(original_path)
            record = {
                "doc_id": doc_id,
                "original_filename": original_filename or f"dokumen{extension}",
                "file_extension": extension,
                "content_hash_hex": content_digest.hex(),
                "signed_hashes": [],
                "created_at": self.utc_now().isoformat(),
                "signers": [],
            }

        signature = self.signer_module.sign_digest(private_key, content_digest)
        public_key_pem = self.key_module.public_key_to_pem(private_key.public_key()).decode("utf-8")
        record["signers"].append({
            "signer_id": uuid.uuid4().hex[:8],
            "owner_id": owner_id,
            "signer_name": signer_name,
            "position": position,
            "institution": institution,
            "signed_date": signed_date,
            "algorithm": "RSA-2048-PSS-SHA256",
            "public_key_pem": public_key_pem,
            "signature_b64": base64.b64encode(signature).decode("utf-8"),
        })

        qr_images = []
        signer_blocks = []
        for entry in record["signers"]:
            metadata = {
                "doc_id": doc_id,
                "signer_id": entry["signer_id"],
                "name": entry["signer_name"],
                "position": entry["position"],
                "institution": entry["institution"],
                "date": entry["signed_date"],
                "hash": record["content_hash_hex"],
                "verify_url": f"{self.verify_base_url}?doc_id={doc_id}",
            }
            qr_images.append(self.qr_module.generate_qr_image(metadata))
            signer_blocks.append({
                "name": entry["signer_name"],
                "position": entry["position"],
                "institution": entry["institution"],
                "date": entry["signed_date"],
            })

        signed_output_path = self.documents_dir / f"{doc_id}_signed{extension}"
        try:
            self.document_module.add_signature_marks(
                original_path, signed_output_path, extension, qr_images, signer_blocks
            )
        except Exception as exc:
            signed_output_path.unlink(missing_ok=True)
            if is_new_document:
                original_path.unlink(missing_ok=True)
            raise SigningError(
                "Server tidak dapat memproses format/struktur berkas ini. "
                "Coba simpan ulang sebagai format Office standar lalu unggah lagi."
            ) from exc

        signed_hash = self.document_module.compute_file_digest(signed_output_path).hex()
        record["file_extension"] = extension
        record.setdefault("signed_hashes", []).append(signed_hash)
        self.save_signature_record(doc_id, record)
        return doc_id, record

    @staticmethod
    def decide_status(integrity_ok, signers, qr_forged):
        if not integrity_ok:
            return "TAMPERED"
        if qr_forged:
            return "QR_FORGED"
        if not signers or not all(signer["signature_valid"] for signer in signers):
            return "KEY_MISMATCH"
        return "VALID"

    def compute_verification(self, document_path, manual_doc_id="", override_public_key=None, file_extension=None):
        file_extension = file_extension or self.document_module.extension_for(document_path, ".pdf")
        try:
            decoded_list = self.document_module.extract_qr_metadata(document_path, file_extension)
        except Exception:
            decoded_list = []

        doc_id = manual_doc_id
        from_qr = False
        if not doc_id and decoded_list:
            candidates = [item.get("doc_id", "") for item in decoded_list
                          if isinstance(item, dict) and item.get("doc_id")]
            registered = [candidate for candidate in candidates
                          if self.valid_doc_id(candidate) and self.load_signature_record(candidate)]
            doc_id = (registered or candidates or [""])[0]
            from_qr = bool(doc_id)

        if not doc_id:
            return {"status": "NO_QR", "error": "Doc ID tidak ditemukan: QR-Code tidak terbaca dan Doc ID tidak diisi"}

        record = self.load_signature_record(doc_id)
        if record is None:
            return {
                "status": "QR_FORGED" if from_qr else "NOT_FOUND",
                "doc_id": doc_id,
                "error": ("QR-Code memuat Doc ID yang tidak terdaftar, kemungkinan QR palsu"
                          if from_qr else f"Doc ID {doc_id} tidak ditemukan"),
            }

        try:
            current_digest = self.document_module.compute_file_digest(document_path)
        except Exception:
            current_digest = None
        stored_digest = bytes.fromhex(record["content_hash_hex"])
        integrity_ok = (current_digest is not None and current_digest.hex() in self.known_hashes(record)
                        and file_extension == self.record_file_extension(record))

        qr_by_signer = {
            item.get("signer_id"): item for item in decoded_list
            if isinstance(item, dict) and item.get("doc_id") == doc_id
        }
        signer_results = []
        for number, entry in enumerate(record["signers"], start=1):
            public_key = override_public_key or self.key_module.load_public_key_from_pem(
                entry["public_key_pem"].encode("utf-8")
            )
            signature_bytes = base64.b64decode(entry["signature_b64"])
            signature_valid = (self.verifier_module.verify_digest(public_key, stored_digest, signature_bytes)
                               if integrity_ok else False)
            metadata = qr_by_signer.get(entry["signer_id"])
            if metadata is None:
                qr_status = "missing"
            elif (metadata.get("hash") == record["content_hash_hex"]
                  and metadata.get("name") == entry["signer_name"]
                  and metadata.get("date") == entry["signed_date"]):
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
                "signature_valid": signature_valid,
                "qr_status": qr_status,
            })

        qr_forged = any(signer["qr_status"] == "mismatch" for signer in signer_results)
        status = self.decide_status(integrity_ok, signer_results, qr_forged)
        return {
            "status": status,
            "doc_id": doc_id,
            "original_filename": record.get("original_filename", ""),
            "file_extension": self.record_file_extension(record),
            "integrity_ok": integrity_ok,
            "signers": signer_results,
            "signers_total": len(signer_results),
            "signers_in_document": sum(signer["qr_status"] == "ok" for signer in signer_results),
            "qr_metadata_found": decoded_list,
            "overall_valid": status == "VALID",
        }

    def verify_bytes(self, data, manual_doc_id="", override_public_key=None, original_filename=""):
        extension = self.document_module.extension_for(original_filename, ".pdf")
        if extension is None:
            return {"status": "TAMPERED", "error": "Format dokumen tidak didukung"}
        temp_path = self.documents_dir / f"verify_temp_{uuid.uuid4().hex[:8]}{extension}"
        temp_path.write_bytes(data)
        try:
            return self.compute_verification(temp_path, manual_doc_id, override_public_key, extension)
        finally:
            temp_path.unlink(missing_ok=True)